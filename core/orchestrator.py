"""
Единая точка входа: проверка гейтов релиза и выполнение перехода.
run_release_check: сбор snapshot → rules → учёт manual_confirmations → результат.
run_release_action: переход по transition_id или имени статуса.
"""
import logging
from typing import Any, Dict, Optional

from core.snapshot_builder import build_release_snapshot
from core.rules import evaluate_gates
from core.release_flow_config import get_release_flow_profile

logger = logging.getLogger(__name__)


def run_release_check(
    jira_service: Any,
    release_key: str,
    profile_name: str = "auto",
    manual_confirmations: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """
    Оценка гейтов релиза. Совместимый с прежним evaluate_release_gates результат.
    """
    safe_release = (release_key or "").strip().upper()
    if not safe_release:
        return {"success": False, "message": "Не указан release_key."}

    snapshot = build_release_snapshot(jira_service, safe_release)
    if not snapshot:
        return {"success": False, "message": f"Релиз {safe_release} не найден."}

    project_key = snapshot.get("project_key", "")
    profile = get_release_flow_profile(
        project_key=project_key,
        requested_profile=profile_name,
    )

    result = evaluate_gates(snapshot, profile)
    confirmations = manual_confirmations or {}

    manual_pending = result["manual_pending"]
    manual_done: list = []
    still_pending: list = []
    for item in manual_pending:
        check_id = item.get("id")
        if confirmations.get(check_id) is True:
            manual_done.append(item)
        else:
            still_pending.append(item)

    result["manual_pending"] = still_pending
    result["manual_done"] = manual_done
    result["ready_for_transition"] = (
        len(result["auto_failed"]) == 0 and len(still_pending) == 0 and bool(result.get("next_allowed_transition"))
    )

    return result


def run_release_action(
    jira_service: Any,
    release_key: str,
    transition_id: Optional[str] = None,
    transition_name: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Выполнить переход релиза. Либо transition_id, либо transition_name.
    Возвращает (ok, message).
    """
    safe_release = (release_key or "").strip().upper()
    if not safe_release:
        return False, "Не указан release_key."

    if transition_id:
        return jira_service.transition_issue_by_id(safe_release, transition_id)
    if transition_name:
        return jira_service.transition_issue(safe_release, transition_name)
    return False, "Не указан transition_id или transition_name."


def format_release_gate_report(result: Dict[str, Any]) -> str:
    """Форматирование отчёта по гейтам (совместимо с прежним format_release_gate_report)."""
    if not result.get("success"):
        return f"❌ {result.get('message', 'Ошибка оценки гейтов')}"

    lines: list = []
    lines.append("=" * 80)
    lines.append(f"🧭 GUIDED CYCLE: {result.get('release_key')}")
    lines.append("=" * 80)
    lines.append(f"Профиль: {result.get('profile_name')} | Проект: {result.get('project_key')}")
    lines.append(f"Текущий этап: {result.get('current_stage')}")
    lines.append(f"Следующий этап: {result.get('next_allowed_transition') or 'нет'}")
    if result.get("next_allowed_transition_id"):
        lines.append(f"Transition ID: {result.get('next_allowed_transition_id')}")
    rqg_qgm = result.get("rqg_qgm", {}) or {}
    if rqg_qgm.get("ok"):
        lines.append("RQG qgm: успешно")
    lines.append("")

    lines.append(f"✅ Авто-гейты пройдены: {len(result.get('auto_passed', []))}")
    for gate in result.get("auto_passed", []):
        details = gate.get("details") or {}
        if gate.get("id") == "rqg_qgm" and details.get("warning_only"):
            lines.append(f"  - {gate.get('title')} (warning: endpoint недоступен, не блокирует)")
        else:
            lines.append(f"  - {gate.get('title')}")
    lines.append(f"❌ Авто-гейты провалены: {len(result.get('auto_failed', []))}")
    for gate in result.get("auto_failed", []):
        lines.append(f"  - {gate.get('title')}: {gate.get('details')}")
        gate_id = gate.get("id")
        if gate_id == "distribution_tab":
            lines.append("    Что сделать: проверь поля 'Ссылка на дистрибутив' и 'КЭ дистрибутива'.")
        elif gate_id == "testing_recommendation":
            lines.append("    Что сделать: в релизе должна быть рекомендация ИФТ = 'Рекомендован'.")
        elif gate_id == "nt_recommendation":
            lines.append("    Что сделать: НТ должна быть 'Не требуется' или 'Версия 2 РЕКОМЕНДОВАН'.")
        elif gate_id == "dt_recommendation":
            lines.append("    Что сделать: ДТ должна быть 'РЕКОМЕНДОВАН'.")
        elif gate_id == "rqg_qgm":
            lines.append("    Что сделать: проверь ответ /rest/release/1/qgm по issueId релиза.")
        elif gate_id == "story_bug_quality":
            lines.append("    Что сделать: закрой bug CT/IFT (только статус 'Закрыт/Closed').")
    lines.append("")

    lines.append(f"📝 Ручные проверки pending: {len(result.get('manual_pending', []))}")
    for check in result.get("manual_pending", []):
        lines.append(f"  - {check.get('id')}: {check.get('message')}")
    if result.get("auto_warnings"):
        lines.append("")
        lines.append(f"⚠️ ВНИМАНИЕ (рекомендации, не блокируют переход): {len(result.get('auto_warnings', []))}")
        for warn in result.get("auto_warnings", []):
            lines.append(f" - {warn.get('title')}")
            if warn.get("id") == "bug_quality":
                for reason in warn.get("details", {}).get("reasons", []):
                    lines.append(f"   * 🐛 {reason}")

    if result.get("manual_pending"):
        lines.append("  Подтвердить вручную можно командой:")
        lines.append(f"  confirm_manual_check({result.get('release_key')}, <check_id>, ok)")
    if result.get("manual_done"):
        lines.append(f"✅ Подтверждено вручную: {len(result.get('manual_done', []))}")
        for check in result.get("manual_done", []):
            lines.append(f"  - {check.get('id')}: подтверждено")
    if result.get("manual_optional"):
        lines.append(f"ℹ️ Опциональные проверки: {len(result.get('manual_optional', []))}")
        for check in result.get("manual_optional", []):
            lines.append(f"  - {check.get('id')}: {check.get('message')}")
    lines.append("")

    if result.get("ready_for_transition"):
        lines.append("🚀 Готов к переходу по workflow.")
    else:
        lines.append("⛔ Переход пока заблокирован (есть непройденные гейты или ручные проверки).")

    lines.append("=" * 80)
    return "\n".join(lines)
