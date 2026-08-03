"""campos de contato na tabela licenses

Revision ID: 0002_contact_fields
Revises: 0001_initial
Create Date: 2026-01-01

"""
from alembic import op
import sqlalchemy as sa

revision = "0002_contact_fields"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("licenses", sa.Column("contact_name", sa.String(length=255), nullable=True))
    op.add_column("licenses", sa.Column("contact_email", sa.String(length=255), nullable=True))
    op.add_column("licenses", sa.Column("contact_phone", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("licenses", "contact_phone")
    op.drop_column("licenses", "contact_email")
    op.drop_column("licenses", "contact_name")
