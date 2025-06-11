"""
Arquivo de configuração centralizada para a automação.
"""

import os
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class SeleniumConfig:
    """Configurações específicas do Selenium."""
    page_load_timeout: int = 30
    element_wait_timeout: int = 20
    download_wait_timeout: int = 60
    retry_attempts: int = 3
    retry_delay: int = 5
    screenshot_on_error: bool = True
    headless_mode: bool = True


@dataclass
class PathConfig:
    """Configurações de caminhos e diretórios."""
    base_dir: Path = Path(__file__).parent
    download_dir: Path = base_dir / "downloads"
    log_dir: Path = base_dir / "logs"
    screenshot_dir: Path = base_dir / "screenshots"
    temp_dir: Path = base_dir / "temp"
    
    def create_directories(self):
        """Cria todos os diretórios necessários."""
        for dir_path in [self.download_dir, self.log_dir, self.screenshot_dir, self.temp_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)


@dataclass
class AppConfig:
    """Configurações gerais da aplicação."""
    app_name: str = "Automação Tickets Migrate"
    version: str = "2.0.0"
    log_level: str = "INFO"
    max_log_files: int = 10
    log_rotation_size: str = "10MB"


class ConfigManager:
    """Gerenciador central de configurações."""
    
    def __init__(self):
        self.selenium = SeleniumConfig()
        self.paths = PathConfig()
        self.app = AppConfig()
        
        # Carrega configurações de ambiente
        self._load_environment_configs()
        
        # Cria diretórios necessários
        self.paths.create_directories()
    
    def _load_environment_configs(self):
        """Carrega configurações das variáveis de ambiente."""
        # Configurações do Selenium
        if os.getenv("HEADLESS_MODE"):
            self.selenium.headless_mode = os.getenv("HEADLESS_MODE", "true").lower() == "true"
        
        if os.getenv("PAGE_LOAD_TIMEOUT"):
            self.selenium.page_load_timeout = int(os.getenv("PAGE_LOAD_TIMEOUT", "30"))
        
        if os.getenv("ELEMENT_WAIT_TIMEOUT"):
            self.selenium.element_wait_timeout = int(os.getenv("ELEMENT_WAIT_TIMEOUT", "20"))
        
        # Configurações de log
        if os.getenv("LOG_LEVEL"):
            self.app.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    def get_chrome_options(self) -> Dict[str, Any]:
        """Retorna configurações otimizadas para o Chrome."""
        return {
            "headless": self.selenium.headless_mode,
            "no_sandbox": True,
            "disable_dev_shm_usage": True,
            "disable_gpu": True,
            "window_size": "1920,1080",
            "disable_extensions": True,
            "disable_popup_blocking": True,
            "disable_blink_features": "AutomationControlled",
            "disable_infobars": True,
            "disable_web_security": True,
            "allow_running_insecure_content": True,
            "disable_features": "VizDisplayCompositor",
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    
    def get_download_preferences(self) -> Dict[str, Any]:
        """Retorna preferências de download para o Chrome."""
        return {
            "download.default_directory": str(self.paths.download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.notifications": 2,
            "profile.managed_default_content_settings.images": 2
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte todas as configurações para dicionário."""
        return {
            "selenium": self.selenium.__dict__,
            "paths": {k: str(v) for k, v in self.paths.__dict__.items()},
            "app": self.app.__dict__
        }


# Instância global de configuração
config = ConfigManager() 