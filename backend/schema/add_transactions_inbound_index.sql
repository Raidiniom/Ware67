-- Inbound dashboard: one company's stock-ins within a date window, polled
-- every few seconds per open tab. Without this each poll scans the company's
-- whole transaction history. ware67_schema.sql already includes it.
CREATE INDEX idx_transactions_company_type_created
    ON transactions (company_id, type, created_at);
