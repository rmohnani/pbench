import { combineReducers } from 'redux';
import ToastReducer from "./toastReducer";
import LoadingReducer from "./loadingReducer";
import PublicControllerReducer from "./publicControllerReducer";

export default combineReducers({
    toastReducer: ToastReducer,
    loading: LoadingReducer,
    contoller: PublicControllerReducer
})
