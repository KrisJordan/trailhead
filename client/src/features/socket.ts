import { PayloadAction, createSlice } from '@reduxjs/toolkit';

export interface SocketState {
    readyState: number;
}

const initialState: SocketState = {
    readyState: 0
}

const socketSlice = createSlice({
    name: 'socket',
    initialState,
    reducers: {
        updateReadyState(state, action: PayloadAction<number>) {
            state.readyState = action.payload;
        }
    }
});

export const { updateReadyState } = socketSlice.actions;
export default socketSlice.reducer;