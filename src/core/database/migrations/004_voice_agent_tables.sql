-- =====================================================
-- VOICE AGENT MULTI-TENANT DATABASE SCHEMA
-- Migration: 004_voice_agent_tables.sql
-- Description: Tables for AI Voice Agent with Twilio, Ultravox, and Odoo CRM
-- =====================================================

-- Tenants (Clients who onboard with their own phone numbers)
CREATE TABLE IF NOT EXISTS voice_tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    industry VARCHAR(50) NOT NULL, -- healthcare, real_estate, insurance, legal, etc.
    timezone VARCHAR(50) DEFAULT 'UTC',
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'trial', 'cancelled')),

    -- Billing
    subscription_plan VARCHAR(50) DEFAULT 'starter',
    monthly_minutes_limit INTEGER DEFAULT 1000,
    minutes_used INTEGER DEFAULT 0,

    -- Settings (JSON for flexibility)
    settings JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_tenants_slug ON voice_tenants(slug);
CREATE INDEX idx_voice_tenants_status ON voice_tenants(status);

-- Phone Numbers (Each tenant can have multiple numbers for different purposes)
CREATE TABLE IF NOT EXISTS voice_phone_numbers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES voice_tenants(id) ON DELETE CASCADE,

    -- Phone Details
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    phone_type VARCHAR(20) NOT NULL CHECK (phone_type IN ('voice', 'whatsapp', 'sms', 'all')),
    country_code VARCHAR(5),

    -- Twilio Configuration
    twilio_sid VARCHAR(50),
    twilio_phone_sid VARCHAR(50),

    -- Display
    display_name VARCHAR(100),
    purpose VARCHAR(100), -- sales, support, appointments, general

    -- Voice Settings
    language VARCHAR(10) DEFAULT 'en-US',
    voice_config_id UUID, -- References voice_configs table

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_phone_numbers_lookup ON voice_phone_numbers(phone_number, is_active);
CREATE INDEX idx_voice_phone_numbers_tenant ON voice_phone_numbers(tenant_id);

-- Voice Configuration (AI personality, voice, prompts per tenant)
CREATE TABLE IF NOT EXISTS voice_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES voice_tenants(id) ON DELETE CASCADE,

    -- AI Agent Identity
    agent_name VARCHAR(100) NOT NULL,
    agent_role VARCHAR(100), -- Sales Representative, Receptionist, Support Agent

    -- Scripts
    greeting_script TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    fallback_responses JSONB DEFAULT '[]',

    -- Voice Settings (Ultravox/ElevenLabs)
    voice_provider VARCHAR(50) DEFAULT 'elevenlabs', -- elevenlabs, playht, azure
    voice_id VARCHAR(100),
    voice_name VARCHAR(100),
    language VARCHAR(10) DEFAULT 'en-US',
    accent VARCHAR(50), -- neutral, british, australian, indian
    speaking_rate FLOAT DEFAULT 1.0 CHECK (speaking_rate BETWEEN 0.5 AND 2.0),
    pitch FLOAT DEFAULT 1.0 CHECK (pitch BETWEEN 0.5 AND 2.0),

    -- Knowledge Base
    industry_knowledge_base TEXT,
    faq_document TEXT,
    product_catalog JSONB,

    -- Behavior
    max_conversation_turns INTEGER DEFAULT 50,
    silence_timeout_ms INTEGER DEFAULT 5000,
    interruption_sensitivity FLOAT DEFAULT 0.5,

    -- Escalation
    escalation_keywords TEXT[] DEFAULT ARRAY['speak to human', 'real person', 'manager', 'supervisor'],
    escalation_sentiment_threshold FLOAT DEFAULT -0.5,

    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_configs_tenant ON voice_configs(tenant_id);

-- Business Hours (When AI answers vs after-hours behavior)
CREATE TABLE IF NOT EXISTS voice_business_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES voice_tenants(id) ON DELETE CASCADE,

    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6), -- 0=Sunday, 6=Saturday
    open_time TIME,
    close_time TIME,
    is_closed BOOLEAN DEFAULT false,

    -- After Hours Behavior
    after_hours_action VARCHAR(50) DEFAULT 'voicemail' CHECK (after_hours_action IN ('voicemail', 'transfer', 'callback', 'message')),
    after_hours_message TEXT,
    after_hours_transfer_number VARCHAR(20),

    UNIQUE(tenant_id, day_of_week)
);

-- Leads (Captured from calls, WhatsApp, web)
CREATE TABLE IF NOT EXISTS voice_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES voice_tenants(id) ON DELETE CASCADE,

    -- Contact Information
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    full_name VARCHAR(255),
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    company_name VARCHAR(255),
    job_title VARCHAR(100),

    -- Address (optional)
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),

    -- Lead Scoring (AI-powered)
    lead_score FLOAT DEFAULT 0.0 CHECK (lead_score BETWEEN 0.0 AND 1.0),
    lead_temperature VARCHAR(10) CHECK (lead_temperature IN ('hot', 'warm', 'cold')),

    -- Qualification Data (BANT: Budget, Authority, Need, Timeline)
    budget_mentioned BOOLEAN,
    budget_range VARCHAR(100),
    is_decision_maker BOOLEAN,
    need_identified TEXT,
    timeline VARCHAR(100), -- immediate, 1-3 months, 6+ months
    qualification_data JSONB DEFAULT '{}',

    -- Source Tracking
    source VARCHAR(50) NOT NULL, -- inbound_call, outbound_call, whatsapp, web, sms
    source_phone_number VARCHAR(20),
    source_campaign VARCHAR(100),
    utm_source VARCHAR(100),
    utm_medium VARCHAR(100),
    utm_campaign VARCHAR(100),
    referrer VARCHAR(255),

    -- Odoo CRM Sync
    odoo_lead_id INTEGER,
    odoo_partner_id INTEGER,
    odoo_sync_status VARCHAR(20) DEFAULT 'pending' CHECK (odoo_sync_status IN ('pending', 'synced', 'failed', 'not_applicable')),
    odoo_last_sync TIMESTAMPTZ,
    odoo_sync_error TEXT,

    -- Pipeline Status
    status VARCHAR(50) DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'qualified', 'meeting_scheduled', 'proposal_sent', 'negotiation', 'won', 'lost', 'unqualified')),
    lost_reason VARCHAR(255),

    -- Assignment
    assigned_to UUID,
    assigned_team VARCHAR(100),

    -- Engagement Metrics
    total_calls INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    last_contact_at TIMESTAMPTZ,
    next_follow_up_at TIMESTAMPTZ,

    -- Tags & Custom Fields
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    custom_fields JSONB DEFAULT '{}',

    -- Consent
    marketing_consent BOOLEAN DEFAULT false,
    consent_timestamp TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_leads_tenant ON voice_leads(tenant_id, status);
CREATE INDEX idx_voice_leads_phone ON voice_leads(phone);
CREATE INDEX idx_voice_leads_email ON voice_leads(email) WHERE email IS NOT NULL;
CREATE INDEX idx_voice_leads_temperature ON voice_leads(tenant_id, lead_temperature);
CREATE INDEX idx_voice_leads_odoo ON voice_leads(odoo_lead_id) WHERE odoo_lead_id IS NOT NULL;
CREATE INDEX idx_voice_leads_follow_up ON voice_leads(next_follow_up_at) WHERE next_follow_up_at IS NOT NULL;

-- Calls (All voice interactions)
CREATE TABLE IF NOT EXISTS voice_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES voice_tenants(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES voice_leads(id) ON DELETE SET NULL,

    -- Twilio Call Data
    twilio_call_sid VARCHAR(50) UNIQUE,
    twilio_parent_call_sid VARCHAR(50), -- For transferred calls
    direction VARCHAR(20) NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    from_number VARCHAR(20) NOT NULL,
    to_number VARCHAR(20) NOT NULL,

    -- Call Metrics
    status VARCHAR(30) DEFAULT 'initiated' CHECK (status IN (
        'initiated', 'ringing', 'in-progress', 'completed',
        'busy', 'no-answer', 'failed', 'canceled'
    )),
    duration_seconds INTEGER,
    ring_duration_seconds INTEGER,
    started_at TIMESTAMPTZ,
    answered_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,

    -- Voice Config Used
    voice_config_id UUID REFERENCES voice_configs(id),

    -- AI Conversation Metrics
    conversation_turns INTEGER DEFAULT 0,
    ai_speaking_time_seconds INTEGER DEFAULT 0,
    user_speaking_time_seconds INTEGER DEFAULT 0,
    silence_time_seconds INTEGER DEFAULT 0,

    -- AI vs Human
    ai_handled BOOLEAN DEFAULT true,
    escalated_to_human BOOLEAN DEFAULT false,
    escalation_reason VARCHAR(255),
    escalated_at TIMESTAMPTZ,
    human_agent_id UUID,

    -- Recording
    recording_enabled BOOLEAN DEFAULT true,
    recording_url TEXT,
    recording_sid VARCHAR(50),
    recording_duration_seconds INTEGER,

    -- Transcript
    transcript JSONB DEFAULT '[]', -- Array of {role, text, timestamp, confidence}
    transcript_summary TEXT,

    -- AI Analysis
    sentiment_score FLOAT CHECK (sentiment_score BETWEEN -1.0 AND 1.0),
    sentiment_trend VARCHAR(20), -- improving, declining, stable
    intent_detected TEXT[],
    entities_extracted JSONB DEFAULT '{}',
    topics_discussed TEXT[],

    -- Outcome
    outcome VARCHAR(50), -- qualified, appointment_set, callback_requested, information_provided, escalated, voicemail
    outcome_details JSONB DEFAULT '{}',
    follow_up_required BOOLEAN DEFAULT false,
    follow_up_date TIMESTAMPTZ,
    follow_up_notes TEXT,

    -- Cost Tracking
    twilio_cost_usd DECIMAL(10,4),
    ultravox_cost_usd DECIMAL(10,4),
    openai_cost_usd DECIMAL(10,4),
    total_cost_usd DECIMAL(10,4),

    -- Quality
    quality_score FLOAT,
    reviewed_by UUID,
    review_notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_calls_tenant_date ON voice_calls(tenant_id, started_at DESC);
CREATE INDEX idx_voice_calls_twilio ON voice_calls(twilio_call_sid);
CREATE INDEX idx_voice_calls_lead ON voice_calls(lead_id);
CREATE INDEX idx_voice_calls_status ON voice_calls(status) WHERE status = 'in-progress';

-- Appointments (Scheduled meetings)
CREATE TABLE IF NOT EXISTS voice_appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES voice_tenants(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES voice_leads(id) ON DELETE SET NULL,
    call_id UUID REFERENCES voice_calls(id) ON DELETE SET NULL,

    -- Appointment Details
    title VARCHAR(255) NOT NULL,
    description TEXT,
    appointment_type VARCHAR(50) DEFAULT 'consultation', -- consultation, demo, viewing, interview, follow_up

    -- Scheduling
    scheduled_at TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    timezone VARCHAR(50) NOT NULL,
    end_at TIMESTAMPTZ GENERATED ALWAYS AS (scheduled_at + (duration_minutes || ' minutes')::INTERVAL) STORED,

    -- Location
    meeting_type VARCHAR(50) DEFAULT 'phone' CHECK (meeting_type IN ('in_person', 'phone', 'video')),
    location VARCHAR(255),
    meeting_link TEXT, -- Zoom, Google Meet, etc.
    dial_in_number VARCHAR(20),

    -- Participants
    lead_name VARCHAR(255),
    lead_phone VARCHAR(20),
    lead_email VARCHAR(255),

    -- Assigned Agent
    assigned_agent_id UUID,
    agent_name VARCHAR(100),
    agent_email VARCHAR(255),
    agent_phone VARCHAR(20),

    -- Status
    status VARCHAR(30) DEFAULT 'scheduled' CHECK (status IN (
        'scheduled', 'confirmed', 'rescheduled', 'completed',
        'cancelled', 'no_show', 'pending_confirmation'
    )),
    cancellation_reason TEXT,
    rescheduled_from UUID, -- Reference to original appointment

    -- Reminders
    reminder_24h_sent BOOLEAN DEFAULT false,
    reminder_24h_sent_at TIMESTAMPTZ,
    reminder_1h_sent BOOLEAN DEFAULT false,
    reminder_1h_sent_at TIMESTAMPTZ,
    confirmation_sent BOOLEAN DEFAULT false,
    confirmation_sent_at TIMESTAMPTZ,

    -- CRM Sync
    odoo_event_id INTEGER,
    odoo_activity_id INTEGER,
    google_calendar_event_id VARCHAR(255),
    outlook_event_id VARCHAR(255),

    -- Outcome
    outcome TEXT,
    outcome_notes TEXT,
    next_steps TEXT,
    follow_up_appointment_id UUID,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_appointments_tenant_date ON voice_appointments(tenant_id, scheduled_at);
CREATE INDEX idx_voice_appointments_status ON voice_appointments(status, scheduled_at);
CREATE INDEX idx_voice_appointments_lead ON voice_appointments(lead_id);
CREATE INDEX idx_voice_appointments_reminders ON voice_appointments(scheduled_at, reminder_24h_sent, reminder_1h_sent)
    WHERE status IN ('scheduled', 'confirmed');

-- Notifications (WhatsApp, SMS, Email)
CREATE TABLE IF NOT EXISTS voice_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES voice_tenants(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES voice_leads(id) ON DELETE SET NULL,
    appointment_id UUID REFERENCES voice_appointments(id) ON DELETE SET NULL,
    call_id UUID REFERENCES voice_calls(id) ON DELETE SET NULL,

    -- Channel & Direction
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('whatsapp', 'sms', 'email', 'push')),
    direction VARCHAR(20) DEFAULT 'outbound' CHECK (direction IN ('outbound', 'inbound')),

    -- Addresses
    to_address VARCHAR(255) NOT NULL,
    from_address VARCHAR(255),

    -- Content
    subject VARCHAR(255), -- For email
    body TEXT NOT NULL,
    body_html TEXT, -- For email
    template_id VARCHAR(100),
    template_data JSONB,
    media_urls TEXT[], -- For MMS/WhatsApp media

    -- Notification Type
    notification_type VARCHAR(50) NOT NULL, -- confirmation, reminder_24h, reminder_1h, follow_up, marketing, transactional

    -- Scheduling
    scheduled_for TIMESTAMPTZ,
    priority INTEGER DEFAULT 0, -- Higher = more urgent

    -- Status
    status VARCHAR(30) DEFAULT 'pending' CHECK (status IN (
        'pending', 'queued', 'sent', 'delivered', 'read',
        'failed', 'cancelled', 'bounced', 'unsubscribed'
    )),

    -- External IDs
    external_id VARCHAR(100), -- Twilio MessageSid, SendGrid ID
    external_status VARCHAR(50),

    -- Timestamps
    queued_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,

    -- Error Handling
    error_code VARCHAR(50),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Cost
    cost_usd DECIMAL(10,4),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_notifications_tenant ON voice_notifications(tenant_id, created_at DESC);
CREATE INDEX idx_voice_notifications_pending ON voice_notifications(scheduled_for, status)
    WHERE status IN ('pending', 'queued');
CREATE INDEX idx_voice_notifications_external ON voice_notifications(external_id);

-- Follow-up Tasks (Automated sequences)
CREATE TABLE IF NOT EXISTS voice_follow_up_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES voice_tenants(id) ON DELETE CASCADE,
    lead_id UUID NOT NULL REFERENCES voice_leads(id) ON DELETE CASCADE,

    -- Task Details
    task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('call', 'email', 'whatsapp', 'sms', 'manual')),
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Sequence Info
    sequence_id VARCHAR(100), -- Groups related follow-ups
    sequence_name VARCHAR(100),
    sequence_step INTEGER, -- Position in sequence (1, 2, 3...)

    -- Scheduling
    scheduled_for TIMESTAMPTZ NOT NULL,
    timezone VARCHAR(50),

    -- Execution
    status VARCHAR(30) DEFAULT 'pending' CHECK (status IN (
        'pending', 'in_progress', 'completed', 'failed',
        'cancelled', 'skipped', 'paused'
    )),
    executed_at TIMESTAMPTZ,
    result JSONB DEFAULT '{}',

    -- Assignment
    is_ai_task BOOLEAN DEFAULT true,
    assigned_to UUID,

    -- Triggers
    trigger_condition JSONB, -- Conditions to execute (e.g., lead not responded)
    stop_condition JSONB, -- Conditions to stop sequence (e.g., lead converted)

    -- Related
    notification_id UUID REFERENCES voice_notifications(id),
    call_id UUID REFERENCES voice_calls(id),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_follow_ups_pending ON voice_follow_up_tasks(scheduled_for, status)
    WHERE status = 'pending';
CREATE INDEX idx_voice_follow_ups_lead ON voice_follow_up_tasks(lead_id);
CREATE INDEX idx_voice_follow_ups_sequence ON voice_follow_up_tasks(sequence_id);

-- Human Agents (For escalation and assignment)
CREATE TABLE IF NOT EXISTS voice_human_agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES voice_tenants(id) ON DELETE CASCADE,

    -- Agent Info
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),

    -- Availability
    is_available BOOLEAN DEFAULT true,
    availability_status VARCHAR(20) DEFAULT 'offline' CHECK (availability_status IN ('online', 'busy', 'away', 'offline')),
    availability_hours JSONB DEFAULT '{}', -- Per day schedule

    -- Capacity
    max_concurrent_calls INTEGER DEFAULT 3,
    current_call_count INTEGER DEFAULT 0,

    -- Skills & Routing
    skills TEXT[] DEFAULT ARRAY[]::TEXT[],
    languages TEXT[] DEFAULT ARRAY['en']::TEXT[],
    specializations TEXT[], -- product types, industries
    priority INTEGER DEFAULT 0, -- Higher = gets calls first

    -- Performance
    total_calls_handled INTEGER DEFAULT 0,
    total_leads_converted INTEGER DEFAULT 0,
    avg_call_duration_seconds INTEGER,
    avg_satisfaction_score FLOAT,

    -- External
    twilio_worker_sid VARCHAR(50),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_human_agents_tenant ON voice_human_agents(tenant_id);
CREATE INDEX idx_voice_human_agents_available ON voice_human_agents(tenant_id, is_available, priority DESC);

-- Conversation Sessions (Real-time state)
CREATE TABLE IF NOT EXISTS voice_conversation_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES voice_tenants(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES voice_leads(id) ON DELETE SET NULL,
    call_id UUID REFERENCES voice_calls(id) ON DELETE SET NULL,

    -- Session Type
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('voice', 'whatsapp', 'sms', 'web')),
    session_type VARCHAR(50) DEFAULT 'conversation', -- conversation, survey, booking

    -- State
    current_state VARCHAR(100), -- greeting, qualifying, scheduling, closing
    state_data JSONB DEFAULT '{}',
    context JSONB DEFAULT '{}', -- Accumulated context

    -- LangGraph Integration
    langgraph_thread_id VARCHAR(100),
    langgraph_checkpoint_id VARCHAR(100),

    -- Ultravox Session
    ultravox_session_id VARCHAR(100),

    -- Timing
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,

    -- Metrics
    total_turns INTEGER DEFAULT 0,
    ai_confidence_avg FLOAT
);

CREATE INDEX idx_voice_sessions_active ON voice_conversation_sessions(tenant_id, channel)
    WHERE ended_at IS NULL;
CREATE INDEX idx_voice_sessions_langgraph ON voice_conversation_sessions(langgraph_thread_id);

-- Analytics Events (For reporting and ML)
CREATE TABLE IF NOT EXISTS voice_analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES voice_tenants(id) ON DELETE CASCADE,

    -- Entity References
    lead_id UUID,
    call_id UUID,
    appointment_id UUID,

    -- Event Info
    event_type VARCHAR(50) NOT NULL,
    event_category VARCHAR(50), -- call, lead, appointment, notification
    event_data JSONB DEFAULT '{}',

    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Create partitions for analytics (last 12 months + current)
CREATE TABLE voice_analytics_events_y2024m01 PARTITION OF voice_analytics_events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE voice_analytics_events_y2024m02 PARTITION OF voice_analytics_events
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- Add more partitions as needed...

CREATE INDEX idx_voice_analytics_tenant_type ON voice_analytics_events(tenant_id, event_type, created_at DESC);

-- =====================================================
-- VIEWS FOR COMMON QUERIES
-- =====================================================

-- Active Calls Dashboard
CREATE OR REPLACE VIEW voice_active_calls_view AS
SELECT
    c.id,
    c.tenant_id,
    t.name as tenant_name,
    c.twilio_call_sid,
    c.direction,
    c.from_number,
    c.to_number,
    c.status,
    c.started_at,
    c.conversation_turns,
    c.ai_handled,
    l.full_name as lead_name,
    l.lead_temperature,
    vc.agent_name
FROM voice_calls c
JOIN voice_tenants t ON c.tenant_id = t.id
LEFT JOIN voice_leads l ON c.lead_id = l.id
LEFT JOIN voice_configs vc ON c.voice_config_id = vc.id
WHERE c.status = 'in-progress';

-- Today's Appointments
CREATE OR REPLACE VIEW voice_todays_appointments_view AS
SELECT
    a.*,
    t.name as tenant_name,
    t.timezone as tenant_timezone,
    l.full_name as lead_full_name,
    l.phone as lead_phone,
    l.email as lead_email,
    l.lead_temperature
FROM voice_appointments a
JOIN voice_tenants t ON a.tenant_id = t.id
LEFT JOIN voice_leads l ON a.lead_id = l.id
WHERE DATE(a.scheduled_at AT TIME ZONE a.timezone) = CURRENT_DATE
  AND a.status IN ('scheduled', 'confirmed')
ORDER BY a.scheduled_at;

-- Lead Conversion Funnel
CREATE OR REPLACE VIEW voice_lead_funnel_view AS
SELECT
    tenant_id,
    lead_temperature,
    status,
    source,
    COUNT(*) as lead_count,
    AVG(lead_score) as avg_score,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as last_7_days,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as last_30_days
FROM voice_leads
GROUP BY tenant_id, lead_temperature, status, source;

-- Pending Reminders
CREATE OR REPLACE VIEW voice_pending_reminders_view AS
SELECT
    a.id as appointment_id,
    a.tenant_id,
    a.lead_id,
    a.scheduled_at,
    a.timezone,
    a.lead_name,
    a.lead_phone,
    a.lead_email,
    CASE
        WHEN NOT a.reminder_24h_sent AND a.scheduled_at - INTERVAL '24 hours' <= NOW() THEN '24h'
        WHEN NOT a.reminder_1h_sent AND a.scheduled_at - INTERVAL '1 hour' <= NOW() THEN '1h'
    END as reminder_type
FROM voice_appointments a
WHERE a.status IN ('scheduled', 'confirmed')
  AND a.scheduled_at > NOW()
  AND (
    (NOT a.reminder_24h_sent AND a.scheduled_at - INTERVAL '24 hours' <= NOW())
    OR (NOT a.reminder_1h_sent AND a.scheduled_at - INTERVAL '1 hour' <= NOW())
  );

-- =====================================================
-- FUNCTIONS & TRIGGERS
-- =====================================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_voice_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables with updated_at
CREATE TRIGGER trigger_voice_tenants_updated_at
    BEFORE UPDATE ON voice_tenants
    FOR EACH ROW EXECUTE FUNCTION update_voice_updated_at();

CREATE TRIGGER trigger_voice_configs_updated_at
    BEFORE UPDATE ON voice_configs
    FOR EACH ROW EXECUTE FUNCTION update_voice_updated_at();

CREATE TRIGGER trigger_voice_leads_updated_at
    BEFORE UPDATE ON voice_leads
    FOR EACH ROW EXECUTE FUNCTION update_voice_updated_at();

CREATE TRIGGER trigger_voice_appointments_updated_at
    BEFORE UPDATE ON voice_appointments
    FOR EACH ROW EXECUTE FUNCTION update_voice_updated_at();

-- Auto-calculate lead temperature based on score
CREATE OR REPLACE FUNCTION calculate_lead_temperature()
RETURNS TRIGGER AS $$
BEGIN
    NEW.lead_temperature = CASE
        WHEN NEW.lead_score >= 0.75 THEN 'hot'
        WHEN NEW.lead_score >= 0.45 THEN 'warm'
        ELSE 'cold'
    END;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_voice_leads_temperature
    BEFORE INSERT OR UPDATE OF lead_score ON voice_leads
    FOR EACH ROW EXECUTE FUNCTION calculate_lead_temperature();

-- Update lead contact timestamp
CREATE OR REPLACE FUNCTION update_lead_last_contact()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'completed' THEN
        UPDATE voice_leads
        SET
            last_contact_at = NOW(),
            total_calls = total_calls + 1
        WHERE id = NEW.lead_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_voice_calls_update_lead
    AFTER INSERT OR UPDATE OF status ON voice_calls
    FOR EACH ROW
    WHEN (NEW.lead_id IS NOT NULL)
    EXECUTE FUNCTION update_lead_last_contact();

-- =====================================================
-- INSERT SAMPLE DATA (Optional - for testing)
-- =====================================================

-- Sample tenant
INSERT INTO voice_tenants (id, name, slug, industry, timezone, settings) VALUES
(
    'a0000000-0000-0000-0000-000000000001',
    'ABC Real Estate',
    'abc-realty',
    'real_estate',
    'America/New_York',
    '{"branding": {"primary_color": "#2563eb"}, "features": {"call_recording": true}}'
) ON CONFLICT DO NOTHING;

-- Sample voice config
INSERT INTO voice_configs (id, tenant_id, agent_name, greeting_script, system_prompt, voice_provider, voice_id, language) VALUES
(
    'b0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000001',
    'Sarah',
    'Hello! Thank you for calling ABC Real Estate. I''m Sarah, your virtual assistant. How may I help you today?',
    'You are Sarah, a friendly and professional real estate assistant for ABC Real Estate. Your role is to:
1. Greet callers warmly and professionally
2. Understand their real estate needs (buying, selling, renting)
3. Collect key information: name, contact, budget, preferred location, timeline
4. Qualify leads based on their readiness and budget
5. Schedule property viewings or agent callbacks
6. Answer common questions about the buying/selling process

Always be helpful, patient, and conversational. If you cannot answer a specific question, offer to connect them with a human agent.',
    'elevenlabs',
    'sarah_voice_clone_id',
    'en-US'
) ON CONFLICT DO NOTHING;
