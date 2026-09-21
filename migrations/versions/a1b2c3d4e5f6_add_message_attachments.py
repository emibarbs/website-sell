"""Agregar columnas de adjuntos a Message (soporte de archivos en el chat)

Revision ID: a1b2c3d4e5f6
Revises: c81e3329401b
Create Date: 2026-09-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'c81e3329401b'
branch_labels = None
depends_on = None


def upgrade():
    # body pasa a ser opcional: un mensaje puede ser solo un adjunto sin texto.
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.alter_column('body', existing_type=sa.Text(), nullable=True)
        batch_op.add_column(sa.Column('attachment_filename', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('attachment_original_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('attachment_mime', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('attachment_size', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_column('attachment_size')
        batch_op.drop_column('attachment_mime')
        batch_op.drop_column('attachment_original_name')
        batch_op.drop_column('attachment_filename')
        batch_op.alter_column('body', existing_type=sa.Text(), nullable=False)
