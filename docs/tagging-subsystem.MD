# Tagging subsystem

The tagging subsystem is loosely coupled.

## SQL Initalization
```
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create tags table
CREATE TABLE tags (
    -- Primary key is composite of category and tag name
    category_name text NOT NULL,
    tag_name text NOT NULL,
    -- Store parent tag reference as composite of category and name
    parent_category text NULL,  
    parent_name text NULL,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (category_name, tag_name),
    -- Self-referential foreign key for hierarchy using composite key
    FOREIGN KEY (parent_category, parent_name) 
        REFERENCES tags (category_name, tag_name)
);

-- Create index for parent tag lookups (for tree traversal)
CREATE INDEX idx_tags_parent ON tags(parent_category, parent_name);

-- Create indexes for efficient text search using trigram similarity
CREATE INDEX idx_tags_name_gin ON tags USING gin (tag_name gin_trgm_ops);
CREATE INDEX idx_tags_category_gin ON tags USING gin (category_name gin_trgm_ops);

-- Create agent_tags table
CREATE TABLE agent_tags (
    agent_id uuid NOT NULL,
    tags text NOT NULL DEFAULT '',  -- Comma-separated list of tags
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (agent_id),
    -- Foreign key to agents table
    FOREIGN KEY (agent_id) REFERENCES agents (id) ON DELETE CASCADE
);

-- Create index for full text search on tags column
CREATE INDEX idx_agent_tags_tags_gin ON agent_tags USING gin (tags gin_trgm_ops);

-- Enable RLS (Row Level Security)
ALTER TABLE tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_tags ENABLE ROW LEVEL SECURITY;

-- Create policies for tags table
CREATE POLICY "Enable read access for all users" ON tags
    FOR SELECT USING (true);

CREATE POLICY "Enable insert for authenticated users only" ON tags
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users only" ON tags
    FOR UPDATE USING (auth.role() = 'authenticated');

-- Create policies for agent_tags table
CREATE POLICY "Enable read access for all users" ON agent_tags
    FOR SELECT USING (true);

CREATE POLICY "Enable insert for authenticated users only" ON agent_tags
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users only" ON agent_tags
    FOR UPDATE USING (auth.role() = 'authenticated');

CREATE POLICY "Enable delete for authenticated users only" ON agent_tags
    FOR DELETE USING (auth.role() = 'authenticated');

-- Create function to validate tag format
CREATE OR REPLACE FUNCTION validate_tag_format()
RETURNS TRIGGER AS $$
DECLARE
    tag text;
    tags text[];
BEGIN
    -- Split the tags string into array
    tags := string_to_array(NEW.tags, ',');

    -- Check each tag
    FOREACH tag IN ARRAY tags
    LOOP
        -- Skip empty tags
        IF trim(tag) = '' THEN
            CONTINUE;
        END IF;

        -- Validate format (category:name)
        IF tag !~ '^[^:]+:[^:]+$' THEN
            RAISE EXCEPTION 'Invalid tag format: %. Expected format: category:name', tag;
        END IF;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to validate tags before insert or update
CREATE TRIGGER validate_tags_before_insert_update
    BEFORE INSERT OR UPDATE ON agent_tags
    FOR EACH ROW
    EXECUTE FUNCTION validate_tag_format();

```