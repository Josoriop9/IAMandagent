-- Add icon and color fields to agents table for customization

ALTER TABLE agents
ADD COLUMN IF NOT EXISTS icon VARCHAR(50) DEFAULT 'robot',
ADD COLUMN IF NOT EXISTS color VARCHAR(50) DEFAULT 'purple';

-- Update existing agents with default values if needed
UPDATE agents 
SET icon = 'robot', color = 'purple'
WHERE icon IS NULL OR color IS NULL;

-- Add comment
COMMENT ON COLUMN agents.icon IS 'Icon identifier for agent (robot, brain, chip, shield, etc.)';
COMMENT ON COLUMN agents.color IS 'Color theme for agent (purple, blue, green, red, etc.)';
