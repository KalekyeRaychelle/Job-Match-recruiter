import React from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import CVheader from './components/CVheader';
import Heading from './components/Heading';
import { JobProvider } from "./context/JobContext";
import ManyCvs from './pages/ManyCvs';

function App() {
  const location = useLocation();
  const path = location.pathname;

  const showCVHeader = path === '/';

  return (
    <div className="App">
      {showCVHeader && <CVheader />}
      {path === '/' && <Heading />}

      <JobProvider>
        <Routes>
          <Route path="/" element={<ManyCvs />} />
        </Routes>
      </JobProvider>
    </div>
  );
}

export default App;
