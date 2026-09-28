"""initial incident schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-09-28 13:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import JSON

# revision identifiers, used by Alembic.
revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Services
    op.create_table(
        'services',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('tier', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('owner_team', sa.String(length=100), nullable=False, server_default='sre'),
        sa.Column('repository_url', sa.String(length=255), nullable=True),
        sa.Column('health_status', sa.String(length=20), nullable=False, server_default='HEALTHY'),
        sa.Column('metadata_json', JSON, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_services_name', 'services', ['name'], unique=True)
    op.create_index('ix_services_tier_health', 'services', ['tier', 'health_status'])

    # 2. Deployments
    op.create_table(
        'deployments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('environment', sa.String(length=50), nullable=False, server_default='production'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='SUCCESS'),
        sa.Column('deployed_by', sa.String(length=100), nullable=False),
        sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('commit_hash', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_deployments_service_id', 'deployments', ['service_id'])
    op.create_index('ix_deployments_environment', 'deployments', ['environment'])
    op.create_index('ix_deployments_deployed_at', 'deployments', ['deployed_at'])
    op.create_index('ix_deployments_service_env_date', 'deployments', ['service_id', 'environment', 'deployed_at'])

    # 3. Incidents
    op.create_table(
        'incidents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('severity', sa.String(length=10), nullable=False, server_default='SEV-2'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='DETECTED'),
        sa.Column('source', sa.String(length=100), nullable=False, server_default='simulator'),
        sa.Column('affected_service', sa.String(length=100), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('symptoms', JSON, nullable=False),
        sa.Column('metadata', JSON, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_incidents_incident_id', 'incidents', ['incident_id'], unique=True)
    op.create_index('ix_incidents_severity', 'incidents', ['severity'])
    op.create_index('ix_incidents_status', 'incidents', ['status'])
    op.create_index('ix_incidents_affected_service', 'incidents', ['affected_service'])
    op.create_index('ix_incidents_detected_at', 'incidents', ['detected_at'])
    op.create_index('ix_incidents_status_severity', 'incidents', ['status', 'severity'])
    op.create_index('ix_incidents_service_status', 'incidents', ['affected_service', 'status'])

    # 4. Alerts
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('alert_id', sa.String(length=100), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False, server_default='simulator'),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='warning'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='firing'),
        sa.Column('payload', JSON, nullable=False),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_alerts_alert_id', 'alerts', ['alert_id'])
    op.create_index('ix_alerts_incident_id', 'alerts', ['incident_id'])
    op.create_index('ix_alerts_severity', 'alerts', ['severity'])
    op.create_index('ix_alerts_status', 'alerts', ['status'])
    op.create_index('ix_alerts_triggered_at', 'alerts', ['triggered_at'])

    # 5. Incident Events (Chronological timeline)
    op.create_table(
        'incident_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('payload', JSON, nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_incident_events_incident_id', 'incident_events', ['incident_id'])
    op.create_index('ix_incident_events_event_type', 'incident_events', ['event_type'])
    op.create_index('ix_incident_events_timestamp', 'incident_events', ['timestamp'])
    op.create_index('ix_incident_events_incident_time', 'incident_events', ['incident_id', 'timestamp'])

    # 6. Investigations
    op.create_table(
        'investigations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('agent_name', sa.String(length=100), nullable=False, server_default='InvestigationAgent'),
        sa.Column('findings', sa.Text(), nullable=False),
        sa.Column('telemetry_summary', JSON, nullable=False),
        sa.Column('correlated_traces', JSON, nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_investigations_incident_id', 'investigations', ['incident_id'])

    # 7. Diagnoses
    op.create_table(
        'diagnoses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('agent_name', sa.String(length=100), nullable=False, server_default='DiagnosisAgent'),
        sa.Column('root_cause_hypothesis', sa.Text(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('chain_of_thought', JSON, nullable=False),
        sa.Column('risk_assessment', sa.Text(), nullable=False, server_default=''),
        sa.Column('diagnosed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_diagnoses_incident_id', 'diagnoses', ['incident_id'])
    op.create_index('ix_diagnoses_diagnosed_at', 'diagnoses', ['diagnosed_at'])
    op.create_index('ix_diagnoses_incident_confidence', 'diagnoses', ['incident_id', 'confidence_score'])

    # 8. Remediation Actions
    op.create_table(
        'remediation_actions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('action_key', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('command_template', sa.Text(), nullable=False),
        sa.Column('safety_level', sa.String(length=20), nullable=False, server_default='SAFE'),
        sa.Column('historical_precedent', sa.String(length=30), nullable=False, server_default='UNTESTED'),
        sa.Column('is_recommended', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_remediation_actions_incident_id', 'remediation_actions', ['incident_id'])
    op.create_index('ix_remediation_actions_action_key', 'remediation_actions', ['action_key'])
    op.create_index('ix_remediation_actions_safety_level', 'remediation_actions', ['safety_level'])
    op.create_index('ix_remediation_actions_is_recommended', 'remediation_actions', ['is_recommended'])
    op.create_index('ix_remediation_incident_rec', 'remediation_actions', ['incident_id', 'is_recommended'])

    # 9. Action Executions
    op.create_table(
        'action_executions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('remediation_action_id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDING_APPROVAL'),
        sa.Column('approved_by', sa.String(length=100), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_output', sa.Text(), nullable=True),
        sa.Column('verification_status', sa.String(length=30), nullable=True),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['remediation_action_id'], ['remediation_actions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_action_executions_incident_id', 'action_executions', ['incident_id'])
    op.create_index('ix_action_executions_remediation_action_id', 'action_executions', ['remediation_action_id'])
    op.create_index('ix_action_executions_status', 'action_executions', ['status'])
    op.create_index('ix_executions_incident_status', 'action_executions', ['incident_id', 'status'])

    # 10. Engineer Feedbacks
    op.create_table(
        'engineer_feedbacks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('engineer_id', sa.String(length=100), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('comments', sa.Text(), nullable=False),
        sa.Column('accuracy_evaluation', sa.String(length=50), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_engineer_feedbacks_incident_id', 'engineer_feedbacks', ['incident_id'])
    op.create_index('ix_engineer_feedbacks_submitted_at', 'engineer_feedbacks', ['submitted_at'])
    op.create_index('ix_feedbacks_incident_rating', 'engineer_feedbacks', ['incident_id', 'rating'])

    # 11. Postmortems
    op.create_table(
        'postmortems',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('root_cause', sa.Text(), nullable=False),
        sa.Column('trigger_event', sa.Text(), nullable=False, server_default=''),
        sa.Column('corrective_actions', JSON, nullable=False),
        sa.Column('timeline', JSON, nullable=False),
        sa.Column('hindsight_retained', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('hindsight_memory_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_postmortems_incident_id', 'postmortems', ['incident_id'], unique=True)
    op.create_index('ix_postmortems_hindsight_retained', 'postmortems', ['hindsight_retained'])


def downgrade() -> None:
    op.drop_table('postmortems')
    op.drop_table('engineer_feedbacks')
    op.drop_table('action_executions')
    op.drop_table('remediation_actions')
    op.drop_table('diagnoses')
    op.drop_table('investigations')
    op.drop_table('incident_events')
    op.drop_table('alerts')
    op.drop_table('incidents')
    op.drop_table('deployments')
    op.drop_table('services')
