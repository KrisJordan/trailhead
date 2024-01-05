import { configureStore } from '@reduxjs/toolkit';
import processReducer from '../features/process';
import filesReducer from '../features/files';
import socketReducer from '../features/socket';
import { websocketMiddlewareFactory } from '../middleware/websocket';
import { Socket } from '../utils/Socket';

const store = configureStore({
    reducer: {
        process: processReducer,
        files: filesReducer,
        socket: socketReducer
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().prepend(websocketMiddlewareFactory(new Socket()))
});

export type RootState = ReturnType<typeof store.getState>;
export default store;