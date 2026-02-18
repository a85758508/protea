import os
import yaml
import importlib.util
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SkillLoader")

class SkillLoader:
    """
    Agent Skill Loader: 从标准接口加载和执行 Agent 技能。
    支持技能发现、验证、沙盒执行（模拟）。
    """
    def __init__(self, skills_dir: str = "/home/ubuntu/skills"):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.loaded_skills: Dict[str, Dict[str, Any]] = {}

    def discover_skills(self) -> List[str]:
        """发现目录下的所有技能"""
        skills = []
        for skill_folder in self.skills_dir.iterdir():
            if skill_folder.is_dir() and (skill_folder / "SKILL.md").exists():
                skills.append(skill_folder.name)
        return skills

    def validate_skill(self, skill_name: str) -> bool:
        """验证技能的完整性"""
        skill_path = self.skills_dir / skill_name
        skill_md = skill_path / "SKILL.md"
        
        if not skill_md.exists():
            logger.error(f"Skill {skill_name} missing SKILL.md")
            return False
            
        try:
            with open(skill_md, 'r') as f:
                content = f.read()
                if content.startswith('---'):
                    _, frontmatter, _ = content.split('---', 2)
                    metadata = yaml.safe_load(frontmatter)
                    if 'name' in metadata and 'description' in metadata:
                        return True
        except Exception as e:
            logger.error(f"Validation failed for {skill_name}: {e}")
        return False

    def load_skill(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """加载技能元数据和指令"""
        if not self.validate_skill(skill_name):
            return None
            
        skill_path = self.skills_dir / skill_name
        skill_md = skill_path / "SKILL.md"
        
        with open(skill_md, 'r') as f:
            content = f.read()
            _, frontmatter, instructions = content.split('---', 2)
            metadata = yaml.safe_load(frontmatter)
            
        skill_data = {
            "metadata": metadata,
            "instructions": instructions.strip(),
            "path": str(skill_path)
        }
        self.loaded_skills[skill_name] = skill_data
        logger.info(f"Skill {skill_name} loaded successfully.")
        return skill_data

    def execute_skill_script(self, skill_name: str, script_name: str, **kwargs) -> Any:
        """在受限环境中执行技能脚本"""
        if skill_name not in self.loaded_skills:
            if not self.load_skill(skill_name):
                raise ValueError(f"Skill {skill_name} not found or invalid.")
                
        script_path = Path(self.loaded_skills[skill_name]["path"]) / script_name
        if not script_path.exists():
            raise FileNotFoundError(f"Script {script_name} not found in skill {skill_name}.")

        # 模拟沙盒执行：使用 importlib 加载模块
        spec = importlib.util.spec_from_file_location(script_name, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if hasattr(module, 'run'):
            return module.run(**kwargs)
        else:
            logger.warning(f"Script {script_name} has no 'run' function.")
            return None

# 示例用法
if __name__ == "__main__":
    loader = SkillLoader()
    # 发现并加载技能的逻辑可以在此处扩展
