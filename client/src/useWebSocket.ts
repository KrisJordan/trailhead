import * as reactUseWebSocket from 'react-use-websocket';

const HOST = window.location.host;
const WS_ENDPOINT = `ws://${HOST}/ws`;

export default function useWebSocket() {
    return reactUseWebSocket.default(WS_ENDPOINT, { share: true, });
}

export const ReadyState = reactUseWebSocket.ReadyState;