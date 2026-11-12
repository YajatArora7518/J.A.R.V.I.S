"""Verified on-demand camera access; no continuous capture or emotion inference."""
from agent.awareness.permissions import permission_manager, privacy_mode_manager


def camera_control(parameters=None, player=None, **kwargs):
    params = parameters or kwargs or {}
    action = str(params.get('action', 'analyze')).lower().strip()
    from core.context_engine import default_context_engine
    from actions import screen_processor
    if player is None:
        player = screen_processor._SCREEN_UI
    if action in ('off', 'disable', 'stop', 'turn_off'):
        from agent.awareness.camera_provider import camera_provider
        camera_provider.disable()
        saved = permission_manager.set_permission('CAMERA_ACCESS', False)
        default_context_engine.camera_active = False
        if player and hasattr(player, 'set_camera_active'):
            player.set_camera_active(False)
        return {'success': bool(saved), 'verified': bool(saved), 'authoritative_response': True,
                'message': 'Camera access band kar diya.' if saved else 'Camera session band hai, par off setting save nahi hui.',
                'camera_ready': False, 'continuous_capture': False}
    if privacy_mode_manager.is_privacy_mode_active():
        return {'success': False, 'verified': False, 'authoritative_response': True,
                'message': 'Privacy pause active hai. Camera use karne se pehle awareness resume karo.', 'error': 'PRIVACY_PAUSED'}
    if action in ('on', 'enable', 'start', 'turn_on'):
        try:
            frame = screen_processor._capture_camera()
            if not frame:
                raise RuntimeError('No camera frame')
            # Only verify hardware here: no upload, saved photo or always-on stream.
            frame_size = len(frame)
            del frame
        except Exception as exc:
            default_context_engine.camera_active = False
            if player and hasattr(player, 'set_camera_active'):
                player.set_camera_active(False)
            return {'success': False, 'verified': False, 'authoritative_response': True,
                    'message': 'Camera khul nahi paaya. Windows camera permission, doosri app ka camera use aur device connection check karo.',
                    'error': 'CAMERA_UNAVAILABLE', 'error_detail': str(exc)[:300], 'camera_ready': False}
        saved = permission_manager.set_permission('CAMERA_ACCESS', True)
        default_context_engine.camera_active = bool(saved)
        if player and hasattr(player, 'set_camera_active'):
            player.set_camera_active(bool(saved))
        return {'success': bool(saved), 'verified': bool(saved), 'authoritative_response': True,
                'message': 'Camera check ho gaya, bhai. Jab bolega tab dekhunga; continuous recording on nahi hai.' if saved else 'Camera hardware chal raha hai, par access setting save nahi hui.',
                'camera_ready': bool(saved), 'frame_bytes': frame_size, 'continuous_capture': False, 'cloud_upload': False}
    if action == 'status':
        enabled = permission_manager.is_granted('CAMERA_ACCESS')
        return {'success': True, 'verified': True, 'authoritative_response': True,
                'message': 'Camera access enabled hai; observation command par fresh hardware check hoga.' if enabled else 'Camera access setting off hai. Camera on bolo to hardware check karke enable karunga.',
                'camera_ready': bool(default_context_engine.camera_active), 'camera_permission': enabled,
                'continuous_capture': False}
    if action not in ('analyze', 'check', 'observe'):
        return {'success': False, 'verified': False, 'message': 'Camera action samajh nahi aaya. Camera on, off, status ya camera dekh bolo.', 'authoritative_response': True}
    # An explicit observation request authorizes one fresh capture. Preserve the
    # actual checked observation/failure, instead of a pretend "analyzing" reply.
    return screen_processor.screen_process({'angle': 'camera', 'text': params.get('query') or params.get('text') or 'Camera mein kya dikh raha hai?'}, player=player)
