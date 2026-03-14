-- ============================================================================
-- Link existing Supabase Auth users to organizations
-- Run this AFTER executing add_user_org_link.sql
-- ============================================================================

-- For each existing user without an organization, create one
DO $$
DECLARE
    user_record RECORD;
    new_api_key TEXT;
BEGIN
    FOR user_record IN 
        SELECT u.id, u.email
        FROM auth.users u
        LEFT JOIN public.organizations o ON o.owner_id = u.id
        WHERE o.id IS NULL
    LOOP
        -- Generate unique API key
        new_api_key := 'hashed_' || encode(gen_random_bytes(32), 'hex');
        
        -- Create organization for this user
        INSERT INTO public.organizations (name, api_key, owner_id)
        VALUES (
            user_record.email || '''s Organization',
            new_api_key,
            user_record.id
        );
        
        RAISE NOTICE 'Created organization for user: %', user_record.email;
    END LOOP;
END $$;

-- Verify - show all users and their organizations
SELECT 
    u.email as user_email,
    o.name as organization_name,
    o.api_key,
    o.created_at
FROM auth.users u
LEFT JOIN public.organizations o ON o.owner_id = u.id
ORDER BY u.created_at DESC;
