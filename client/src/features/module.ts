import { PayloadAction, createSlice } from '@reduxjs/toolkit';

export interface IntType {
    type: 'int';
    value: number;
}

export interface FloatType {
    type: 'float';
    value: number;
}

export interface StringType {
    type: 'str';
    value: string;
}

export interface BoolType {
    type: 'bool';
    value: boolean;
}

export interface NoneType {
    type: 'none';
}

export interface ListType {
    type: 'list';
    items: PythonValue[];
}

export interface DictType {
    type: 'dict';
    keys: PythonValue[];
    values: PythonValue[];
}

export interface UnknownType {
    type: 'unknown';
    python_type: string;
    value: string;
}

export interface Parameter {
    name: string;
    type: string;
    default: string;
}

export interface FunctionType {
    type: 'function';
    name: string;
    doc: string;
    parameters: ParameterInfo[];
    return_type: string;
    source: string;
}

export type PrimitiveType = IntType | FloatType | StringType | BoolType;

export type PythonValue = IntType |
    FloatType |
    StringType |
    BoolType |
    FunctionType |
    NoneType |
    ListType |
    DictType |
    UnknownType
    ;

export interface Context {
    type: 'context';
    values: { [key: string]: PythonValue };
}

export interface ParameterInfo {
    name: string;
    type: string;
}

export interface FunctionInfo {
    name: string;
    doc: string;
    parameters: ParameterInfo[];
    return_type: string;
    source: string;
}

export interface ModuleInfo {
    name: string;
    doc: string;
    top_level_functions: any[];
    top_level_calls: string[];
    global_vars: { [key: string]: any };
}

export interface ModuleState {
    selected: string | null;
    info: ModuleInfo | null;
    context: Context | null;
}

const initialState: ModuleState = {
    selected: null,
    info: null,
    context: null
}

const moduleSlice = createSlice({
    name: 'module',
    initialState,
    reducers: {
        clearModule(state) {
            state.selected = null;
            state.info = null;
            state.context = null;
        },
        setModule(state, action: PayloadAction<{ module: string, info: ModuleInfo }>) {
            state.selected = action.payload.module;
            state.info = action.payload.info;
        },
        setContext(state, action: PayloadAction<Context>) {
            state.context = action.payload;
        }
    }
});

export const { clearModule, setModule, setContext } = moduleSlice.actions;
export default moduleSlice.reducer;