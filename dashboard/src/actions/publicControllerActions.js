import * as types from "./types";
import API from "../utils/api";

export const fetchPublicDatasets = () => async( dispatch ) => { 
    try {
        dispatch({type:types.LOADING});
        const response = await API.get('api/v1/datasets/list?metadata=dataset.created&access=public');
        if(response.status === 200 && response.data) {
            dispatch({
                type: 'GET_PUBLIC_CONTROLLERS',
                payload: response?.data
            });
        }
        dispatch({type:types.COMPLETED});
        return response?.data;
        
    } catch (error) {
        return error;        
    }
}