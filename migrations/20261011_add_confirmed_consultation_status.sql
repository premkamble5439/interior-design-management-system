ALTER TABLE consultations
MODIFY COLUMN status ENUM(
    'pending',
    'contacted',
    'confirmed',
    'completed',
    'cancelled'
) NOT NULL DEFAULT 'pending';
