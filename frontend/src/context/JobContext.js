import React, { createContext, useState, useContext } from 'react';

const JobContext = createContext();


export const useJobContext = () => {
  return useContext(JobContext);
};


export const JobProvider = ({ children }) => {
  const [jobDescription, setJobDescription] = useState('');

  return (
    <JobContext.Provider value={{ jobDescription, setJobDescription }}>
      {children}
    </JobContext.Provider>
  );
};
