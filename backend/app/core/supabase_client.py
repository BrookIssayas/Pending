from supabase import Client, create_client

from app.core.config import settings

_supabase_client: Client | None = None
_supabase_admin_client: Client | None = None


def get_supabase_client() -> Client:
    """Get Supabase client instance (singleton to preserve PKCE state)"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    return _supabase_client

def get_supabase_admin_client() -> Client:
    """Get Supabase admin client instance (singleton).
    Uses the service_role key — bypasses RLS. For trusted backend operations only
    (e.g. reading/writing OAuth provider tokens, background jobs).
    Never expose this client or its key to the frontend.
    """
    global _supabase_admin_client
    if _supabase_admin_client is None:
        _supabase_admin_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ADMIN_KEY)
    return _supabase_admin_client