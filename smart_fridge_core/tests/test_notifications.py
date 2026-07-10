from unittest.mock import patch, MagicMock
from services.notification_service.pusher import NotificationService


@patch("services.notification_service.pusher.settings")
def test_notification_service_not_initialized(mock_settings):
    mock_settings.FIREBASE_CREDENTIALS_PATH = None
    service = NotificationService()
    assert service.initialized is False


@patch("services.notification_service.pusher.settings")
def test_send_push_not_initialized(mock_settings):
    mock_settings.FIREBASE_CREDENTIALS_PATH = None
    service = NotificationService()
    result = service.send_push_notification("token", "Title", "Body")
    assert result is None


@patch("services.notification_service.pusher.settings")
@patch("services.notification_service.pusher.messaging")
@patch("services.notification_service.pusher.firebase_admin")
@patch("services.notification_service.pusher.credentials")
def test_send_push_success(mock_creds, mock_firebase, mock_messaging, mock_settings):
    mock_settings.FIREBASE_CREDENTIALS_PATH = "/fake/path.json"
    mock_creds.Certificate.return_value = MagicMock()
    mock_messaging.send.return_value = "projects/test/messages/123"

    service = NotificationService()
    result = service.send_push_notification("device_token", "Test", "Body")
    assert result == "projects/test/messages/123"
    mock_messaging.send.assert_called_once()


@patch("services.notification_service.pusher.settings")
@patch("services.notification_service.pusher.messaging")
@patch("services.notification_service.pusher.firebase_admin")
@patch("services.notification_service.pusher.credentials")
def test_send_push_error(mock_creds, mock_firebase, mock_messaging, mock_settings):
    mock_settings.FIREBASE_CREDENTIALS_PATH = "/fake/path.json"
    mock_creds.Certificate.return_value = MagicMock()
    mock_messaging.send.side_effect = Exception("Invalid token")

    import pytest
    service = NotificationService()
    with pytest.raises(Exception, match="Invalid token"):
        service.send_push_notification("bad_token", "Title", "Body")


@patch("services.notification_service.pusher.settings")
@patch("services.notification_service.pusher.messaging")
@patch("services.notification_service.pusher.firebase_admin")
@patch("services.notification_service.pusher.credentials")
def test_send_expiration_alerts(mock_creds, mock_firebase, mock_messaging, mock_settings):
    mock_settings.FIREBASE_CREDENTIALS_PATH = "/fake/path.json"
    mock_creds.Certificate.return_value = MagicMock()
    mock_messaging.send.return_value = "ok"

    service = NotificationService()
    service.send_expiration_alerts(
        user_tokens=["token1"],
        expired_items=["Milk", "Cheese"],
        expiring_items=["Bread"],
    )
    assert mock_messaging.send.call_count == 2
