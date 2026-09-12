"""The production configuration guard."""
import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import Settings

SAFE = {
    "ENVIRONMENT": "production",
    "JWT_SECRET": "x" * 48,
    "CORS_ORIGINS": ["https://app.example.com"],
    "SEO_ALLOW_PRIVATE_TARGETS": False,
    "DEBUG": False,
    "API_KEY_ENCRYPTION_KEY": Fernet.generate_key().decode(),
}


def test_safe_production_config_is_accepted():
    assert Settings(**SAFE).is_production is True


def test_development_defaults_are_left_alone():
    settings = Settings(ENVIRONMENT="development")
    assert settings.is_production is False


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"JWT_SECRET": "CHANGE_ME_IN_PRODUCTION_USE_A_LONG_RANDOM_STRING"}, "JWT_SECRET"),
        ({"JWT_SECRET": "short"}, "JWT_SECRET"),
        ({"CORS_ORIGINS": ["*"]}, "CORS_ORIGINS"),
        ({"SEO_ALLOW_PRIVATE_TARGETS": True}, "SEO_ALLOW_PRIVATE_TARGETS"),
        ({"DEBUG": True}, "DEBUG"),
        ({"API_KEY_ENCRYPTION_KEY": ""}, "API_KEY_ENCRYPTION_KEY"),
    ],
)
def test_unsafe_production_config_refuses_to_boot(override, expected):
    with pytest.raises(ValidationError) as excinfo:
        Settings(**{**SAFE, **override})
    assert expected in str(excinfo.value)
