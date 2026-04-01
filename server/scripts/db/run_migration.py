"""Run alembic migration."""
from alembic.config import Config
from alembic import command

if __name__ == "__main__":
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    print("Migration completed!")
