import { configureStore } from '@reduxjs/toolkit';
import processReducer from '../features/process';
import filesReducer from '../features/files';
import socketReducer from '../features/socket';
import moduleReducer from '../features/module';
import { websocketMiddlewareFactory } from '../middleware/websocket';
import { Socket } from '../utils/Socket';
import { runsocketMiddlewareFactory } from '../middleware/runsocket';

const store = configureStore({
    reducer: {
        process: processReducer,
        files: filesReducer,
        socket: socketReducer,
        module: moduleReducer,
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware()
        .concat([websocketMiddlewareFactory(new Socket()), runsocketMiddlewareFactory()])
});

export type RootState = ReturnType<typeof store.getState>;
export default store;