INSERT INTO facilities (code, name, outbound_enabled) VALUES
    ('SEA', 'Seattle', 1),
    ('PDX', 'Portland', 1),
    ('DFW', 'Dallas Fort Worth', 1),
    ('BOI', 'Boise', 0);

INSERT INTO trailers (trailer_id, status, last_inspection) VALUES
    ('TRL-204', 'ACTIVE', '2026-07-15'),
    ('TRL-207', 'ACTIVE', '2026-07-28'),
    ('TRL-311', 'MAINTENANCE', '2026-05-20'),
    ('TRL-402', 'ACTIVE', '2026-08-11'),
    ('TRL-455', 'RETIRED', '2025-11-02');

-- SHP-1007 is the canonical demo case: no trailer assigned at all.
-- SHP-1010 has a trailer that the nightly sweep moved to MAINTENANCE.
-- SHP-1013 is valid except that BOI is inbound only.
INSERT INTO shipments (shipment_id, status, trailer_id, location, priority, created_at) VALUES
    ('SHP-1007', 'CREATED', NULL, 'SEA', 'STANDARD', '2026-08-30 04:12:03'),
    ('SHP-1008', 'IN_TRANSIT', 'TRL-204', 'PDX', 'EXPRESS', '2026-08-30 04:15:41'),
    ('SHP-1010', 'CREATED', 'TRL-311', 'DFW', 'EXPRESS', '2026-08-30 08:11:22'),
    ('SHP-1013', 'CREATED', 'TRL-402', 'BOI', 'STANDARD', '2026-08-30 09:04:55'),
    ('SHP-1014', 'READY_FOR_DISPATCH', 'TRL-207', 'SEA', 'ECONOMY', '2026-08-30 13:22:31'),
    ('SHP-1002', 'DELIVERED', 'TRL-204', 'SEA', 'STANDARD', '2026-08-28 22:05:00');
