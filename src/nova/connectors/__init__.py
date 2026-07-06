"""External-connector interface and registry — C0 contract (SPEC §15).

Belongs here: the Connector protocol (pull/plan/apply/health + declared CredRefs)
and the entry-point registry with connector_api version checks. Concrete
connectors (jira, github, jenkins...) ship as separate wheels registered under
the nova.connectors entry point — never in this package. Agent access rules:
pull/plan may be exposed as tools; apply is core-only, post-gate, never
agent-callable.
"""
