const messageQueue: [((arg: any) => void)?] = [];
window.addEventListener(
    "message",
    (event: MessageEvent<{ source: string; payload: any }>) => {
        if (event.data.source !== "gui-template-parent") return;

        if (messageQueue.length > 0) {
            const handler = messageQueue.shift()!;
            handler(event.data.payload);
        }
    },
);

export function executeCode<T>(code: string) {
    return new Promise<T>((res, rej) => {
        function receivePayload(payload: T) {
            res(payload);
        }

        messageQueue.push(receivePayload);

        window.parent.postMessage(
            {
                source: "gui-template-child",
                payload: code,
            },
            "*",
        );
    });
}
