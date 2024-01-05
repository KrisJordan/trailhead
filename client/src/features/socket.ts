import { PayloadAction, createSlice } from '@reduxjs/toolkit';
import { ReadyState } from '../utils/Socket';

export interface SocketState {
    readyState: ReadyState;
}

const initialState: SocketState = {
    readyState: ReadyState.UNINITIALIZED
}

const socketSlice = createSlice({
    name: 'socket',
    initialState,
    reducers: {
        updateReadyState(state, action: PayloadAction<ReadyState>) {
            state.readyState = action.payload;
        }
    }
});

export const { updateReadyState } = socketSlice.actions;
export default socketSlice.reducer;