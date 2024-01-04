import * as reactUseWebSocket from 'react-use-websocket';

const HOST = window.location.host;
const PROTOCOL = window.location.protocol === 'http:' ? 'ws:' : 'wss:';
const WS_ENDPOINT = `${PROTOCOL}//${HOST}/ws`;

export default function useWebSocket() {
    return reactUseWebSocket.default(WS_ENDPOINT, { share: true, });
}

export const ReadyState = reactUseWebSocket.ReadyState;