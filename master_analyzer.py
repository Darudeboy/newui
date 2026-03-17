"""
Заглушка для совместимости с UI: MasterServicesAnalyzer и ConfluenceDeployPlanGenerator.
При необходимости перенести полную реализацию из старого проекта.
"""
from typing import Any, Dict


class MasterServicesAnalyzer:
    """Заглушка: анализ сервисов в master."""

    def analyze_release(self, release_key: str) -> Dict[str, Any]:
        return {
            "success": False,
            "message": "Master analyzer не настроен (используйте реализацию из старого проекта).",
            "total_tasks": 0,
            "total_prs": 0,
            "services": [],
        }


class ConfluenceDeployPlanGenerator:
    """Заглушка: генерация deploy plan в Confluence."""

    def generate_deploy_plan(
        self,
        release_key: str,
        analysis: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return {
            "success": False,
            "message": "ConfluenceDeployPlanGenerator не настроен.",
        }
