from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    foundry_api_token: str = "change-me"
    bambu_printer_ip: str = ""
    bambu_printer_serial: str = ""
    bambu_printer_access_code: str = ""
    anthropic_api_key: str = ""
    ntfy_topic: str = "foundry-prints"
    ntfy_server: str = "https://ntfy.sh"
    database_url: str = "sqlite+aiosqlite:///storage/foundry.db"
    orcaslicer_path: str = "/Applications/OrcaSlicer.app/Contents/MacOS/orca-slicer"
    openscad_path: str = "/usr/local/bin/openscad"
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "foundry/1.0"
    foundry_env: str = "development"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
