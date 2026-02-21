-- ============================================================================
-- Add owner_id to organizations table to link with Supabase Auth users
-- ============================================================================

-- Add owner_id column if it doesn't exist
ALTER TABLE organizations 
ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES auth.users(id);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_organizations_owner ON organizations(owner_id);

-- Update RLS policy to allow users to see their own organization
DROP POLICY IF EXISTS organizations_isolation ON organizations;

CREATE POLICY organizations_user_access ON organizations
    FOR ALL
    USING (owner_id = auth.uid());

-- ============================================================================
-- Function to auto-create organization on user signup
-- ============================================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    new_api_key TEXT;
BEGIN
    -- Generate unique API key
    new_api_key := 'hashed_' || encode(gen_random_bytes(32), 'hex');
    
    -- Create organization for new user
    INSERT INTO public.organizations (name, api_key, owner_id)
    VALUES (
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email) || '''s Organization',
        new_api_key,
        NEW.id
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop trigger if exists
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Create trigger to run function on new user signup
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- ============================================================================
-- SUCCESS! Now when a user signs up:
-- 1. Supabase Auth creates user in auth.users
-- 2. Trigger fires and creates organization in organizations table
-- 3. Organization is linked to user via owner_id
-- 4. Unique API key is generated
-- ============================================================================
