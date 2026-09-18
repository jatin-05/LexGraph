from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.config import get_settings


settings = get_settings()

supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_secret_key,
    # options=ClientOptions(
    #     auto_refresh_token=False,
    #     persist_session=False,
    # ),
)