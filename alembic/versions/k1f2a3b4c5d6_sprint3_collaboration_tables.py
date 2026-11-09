"""sprint 3: evidencias, colaboraciones entre areas y menciones

Revision ID: k1f2a3b4c5d6
Revises: j0e1f2a3b4c5
Create Date: 2026-10-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "k1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "j0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("report_evidences"):
        op.create_table(
            "report_evidences",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("report_id", sa.Integer(), nullable=False),
            sa.Column("uploader_id", sa.Integer(), nullable=False),
            sa.Column("file_url", sa.String(length=1024), nullable=False),
            sa.Column("caption", sa.String(length=500), nullable=True),
            sa.Column(
                "stage",
                sa.Enum("antes", "durante", "despues", name="evidencestageenum"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
            sa.ForeignKeyConstraint(["uploader_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_report_evidences_report_id",
            "report_evidences",
            ["report_id"],
            unique=False,
        )
        op.create_index(
            "ix_report_evidences_uploader_id",
            "report_evidences",
            ["uploader_id"],
            unique=False,
        )

    if not _table_exists("report_collaborations"):
        op.create_table(
            "report_collaborations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("report_id", sa.Integer(), nullable=False),
            sa.Column("requested_by_id", sa.Integer(), nullable=False),
            sa.Column("from_specialty_id", sa.Integer(), nullable=True),
            sa.Column("to_specialty_id", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(length=1000), nullable=False),
            sa.Column(
                "status",
                sa.Enum(
                    "solicitada",
                    "aceptada",
                    "completada",
                    "rechazada",
                    name="collaborationstatusenum",
                ),
                nullable=False,
                server_default="solicitada",
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
            sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["from_specialty_id"], ["specialties.id"]),
            sa.ForeignKeyConstraint(["to_specialty_id"], ["specialties.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_report_collaborations_report_id",
            "report_collaborations",
            ["report_id"],
            unique=False,
        )
        op.create_index(
            "ix_report_collaborations_requested_by_id",
            "report_collaborations",
            ["requested_by_id"],
            unique=False,
        )

    # La tabla de comentarios (HU-13) se mergeó sin migración; se crea aquí
    # para que comment_mentions pueda referenciarla.
    if not _table_exists("comments"):
        op.create_table(
            "comments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("report_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_comments_report_id",
            "comments",
            ["report_id"],
            unique=False,
        )
        op.create_index(
            "ix_comments_user_id",
            "comments",
            ["user_id"],
            unique=False,
        )

    if not _table_exists("comment_mentions"):
        op.create_table(
            "comment_mentions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("comment_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("comment_id", "user_id", name="uq_comment_mention"),
        )
        op.create_index(
            "ix_comment_mentions_comment_id",
            "comment_mentions",
            ["comment_id"],
            unique=False,
        )
        op.create_index(
            "ix_comment_mentions_user_id",
            "comment_mentions",
            ["user_id"],
            unique=False,
        )


def downgrade() -> None:
    if _table_exists("comment_mentions"):
        op.drop_index("ix_comment_mentions_user_id", table_name="comment_mentions")
        op.drop_index("ix_comment_mentions_comment_id", table_name="comment_mentions")
        op.drop_table("comment_mentions")

    if _table_exists("comments"):
        op.drop_index("ix_comments_user_id", table_name="comments")
        op.drop_index("ix_comments_report_id", table_name="comments")
        op.drop_table("comments")

    if _table_exists("report_collaborations"):
        op.drop_index(
            "ix_report_collaborations_requested_by_id",
            table_name="report_collaborations",
        )
        op.drop_index(
            "ix_report_collaborations_report_id",
            table_name="report_collaborations",
        )
        op.drop_table("report_collaborations")

    if _table_exists("report_evidences"):
        op.drop_index("ix_report_evidences_uploader_id", table_name="report_evidences")
        op.drop_index("ix_report_evidences_report_id", table_name="report_evidences")
        op.drop_table("report_evidences")
