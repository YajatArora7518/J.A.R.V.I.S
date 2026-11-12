"""Report actual registered capabilities without probing accounts or changing rights."""
def assistant_access(parameters=None, **kwargs):
    from core.tool_registry import default_tool_registry
    from agent.awareness.permissions import permission_manager
    from core.ai_policy import is_cloud_ai_allowed
    import platform
    tools = default_tool_registry.list_tools()
    administrator = None
    if platform.system() == 'Windows':
        try:
            import ctypes
            administrator = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            pass
    message = (f'Abhi {len(tools)} registered tools hain. Apps, files, browser, messages aur laptop settings ka kaam '
               'tumhare current Windows/account access aur actual available tool se karunga. '
               'Registered tool hona account login ya successful action ka proof nahi hai. '
               f'Camera access setting {"on" if permission_manager.is_granted("CAMERA_ACCESS") else "off"} hai; '
               'camera dekh bolo to fresh observation lunga. '
               'Shutdown/restart, delete aur elevated changes par exact confirmation lagegi. '
               'Internet ka jawab source se verify karunga; access ya evidence na mile to saaf bataunga.')
    return {'success': True, 'verified': True, 'message': message, 'authoritative_response': True,
            'data': {'registered_tools': tools, 'windows_admin': administrator,
                     'camera_permission': permission_manager.is_granted('CAMERA_ACCESS'),
                     'cloud_ai_allowed': is_cloud_ai_allowed(), 'account_authentication': 'not_probed',
                     'disruptive_confirmation_required': True}}
