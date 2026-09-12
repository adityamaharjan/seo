"""add site_audits and site_audit_pages for multi-page crawls

Revision ID: a3f7b2c91d40
Revises: d1995d82cfa6
Create Date: 2026-09-12 09:40:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a3f7b2c91d40'
down_revision: Union[str, None] = 'd1995d82cfa6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'site_audits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('start_url', sa.String(length=2048), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column(
            'status',
            sa.Enum('pending', 'running', 'done', 'failed', name='siteauditstatus'),
            nullable=False,
        ),
        sa.Column('job_id', sa.String(length=64), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('quota_refunded', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('max_pages', sa.Integer(), nullable=False),
        sa.Column('pages_crawled', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('pages_failed', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('discovery_source', sa.String(length=16), nullable=True),
        sa.Column('overall_score', sa.Integer(), nullable=True),
        sa.Column('overall_grade', sa.String(length=2), nullable=True),
        sa.Column('results', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_site_audits_id'), 'site_audits', ['id'])
    op.create_index(op.f('ix_site_audits_user_id'), 'site_audits', ['user_id'])
    op.create_index(op.f('ix_site_audits_domain'), 'site_audits', ['domain'])
    op.create_index(op.f('ix_site_audits_status'), 'site_audits', ['status'])
    op.create_index(op.f('ix_site_audits_job_id'), 'site_audits', ['job_id'])
    op.create_index('ix_site_audits_user_created', 'site_audits', ['user_id', 'created_at'])

    op.create_table(
        'site_audit_pages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('audit_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('final_url', sa.String(length=2048), nullable=True),
        sa.Column('title', sa.String(length=512), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('overall_score', sa.Integer(), nullable=True),
        sa.Column('overall_grade', sa.String(length=2), nullable=True),
        sa.Column('ttfb_ms', sa.Float(), nullable=True),
        sa.Column('load_time_ms', sa.Float(), nullable=True),
        sa.Column('issue_counts', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('results', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['audit_id'], ['site_audits.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_site_audit_pages_id'), 'site_audit_pages', ['id'])
    op.create_index(op.f('ix_site_audit_pages_audit_id'), 'site_audit_pages', ['audit_id'])
    op.create_index(
        'ix_site_audit_pages_audit_score', 'site_audit_pages', ['audit_id', 'overall_score']
    )


def downgrade() -> None:
    op.drop_index('ix_site_audit_pages_audit_score', table_name='site_audit_pages')
    op.drop_index(op.f('ix_site_audit_pages_audit_id'), table_name='site_audit_pages')
    op.drop_index(op.f('ix_site_audit_pages_id'), table_name='site_audit_pages')
    op.drop_table('site_audit_pages')

    op.drop_index('ix_site_audits_user_created', table_name='site_audits')
    op.drop_index(op.f('ix_site_audits_job_id'), table_name='site_audits')
    op.drop_index(op.f('ix_site_audits_status'), table_name='site_audits')
    op.drop_index(op.f('ix_site_audits_domain'), table_name='site_audits')
    op.drop_index(op.f('ix_site_audits_user_id'), table_name='site_audits')
    op.drop_index(op.f('ix_site_audits_id'), table_name='site_audits')
    op.drop_table('site_audits')
