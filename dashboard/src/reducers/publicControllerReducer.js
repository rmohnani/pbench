import { GET_PUBLIC_CONTROLLERS } from "../actions/types";

const initialState = {
    publicData: []
}

const PublicControllerReducer = (state = initialState, action = {}) => {
    const { type, payload } = action;
    switch (type) {
        case GET_PUBLIC_CONTROLLERS:
            return {
                ...state,
                publicData: [...payload]
            }
        default:
            return state;
    }
}

export default PublicControllerReducer;
