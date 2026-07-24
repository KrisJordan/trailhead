import { configureStore } from '@reduxjs/toolkit';
import processReducer from '../features/process';
import filesReducer from '../features/files';
import socketReducer from '../features/socket';
import moduleReducer from '../features/module';
import testsReducer from '../features/tests';
import { websocketMiddlewareFactory } from '../middleware/websocket';
import { runsocketMiddlewareFactory } from '../middleware/runsocket';
import { testsocketMiddlewareFactory } from '../middleware/testsocket';

const store = configureStore({
    reducer: {
        process: processReducer,
        files: filesReducer,
        socket: socketReducer,
        module: moduleReducer,
        tests: testsReducer,
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware()
        .concat([
            websocketMiddlewareFactory(),
            runsocketMiddlewareFactory(),
            testsocketMiddlewareFactory(),
        ])
});

export type RootState = ReturnType<typeof store.getState>;
export default store;
