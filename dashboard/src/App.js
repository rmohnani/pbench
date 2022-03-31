import React from 'react'
import { BrowserRouter as Router,Route,Routes } from 'react-router-dom'
import { TableWithFavorite } from './modules/components/TableComponent'

function App() {
  return (
    <>
    <Router>
      <Routes>
    <Route exact path="/" element={<TableWithFavorite/>}/>
    </Routes>
    </Router>
    </>
  )
}

export default App
