import React, { useState, useEffect } from 'react';
import '../styles/ManyCvs.css';
import JSZip from "jszip";
import { saveAs } from "file-saver";

const ManyCvs = () => {
  const [selectedOptions, setSelectedOptions] = useState([]);
  const [cutoff, setCutoff] = useState(70); 
  
  const handleDownloadMatchingCVs = async () => {
    if (!analysisResult || analysisResult.length === 0) {
      alert("No analysis results to filter.");
      return;
    }
  
    const matchedFiles = files.filter(file => {
      const result = analysisResult.find(r => r.filename === file.name);
      return result && result.feedback && result.feedback.match_percentage >= cutoff;
    });
  
    if (matchedFiles.length === 0) {
      alert("No CVs meet the selected cutoff.");
      return;
    }
  
    const zip = new JSZip();
  
   
    for (const file of matchedFiles) {
      const fileData = await file.arrayBuffer();
      zip.file(file.name, fileData);
    }
  
    
    const content = await zip.generateAsync({ type: "blob" });
    saveAs(content, `matched_cvs_cutoff_${cutoff}.zip`);
  };

  const handleOptionChange = (e) => {
    const { value, checked } = e.target;

    if (value === "all") {
        setSelectedOptions(checked ? ["all"] : []);
        return;
    }

    let updated = [...selectedOptions].filter(opt => opt !== "all");

    if (checked) {
        if (updated.length >= 3) {
          alert("You can only select up to 3 options.");
          return;
        }
        updated.push(value);
      } else {
        updated = updated.filter(opt => opt !== value);
    }

      setSelectedOptions(updated);
    };

  
  const [files, setFiles] = useState(() => {
      const stored = localStorage.getItem('cvFiles');
      return stored ? JSON.parse(stored) : [];
  });
  
 const [jobDescriptionFile, setJobDescriptionFile] = useState(null);
const [jdFileName, setJdFileName] = useState(() => {
  return localStorage.getItem('jobDescriptionFileName') || '';
});
  
  const [analysisResult, setAnalysisResult] = useState(() => {
    const stored = localStorage.getItem('analysisResultMany');
    return stored ? JSON.parse(stored) : null;
  });
  
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    const handleBeforeUnload = () => {
      localStorage.removeItem('jobDescriptionFileName');
      localStorage.removeItem('cvFiles');
      localStorage.removeItem('analysisResultMany'); 
    };
  
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, []);
  
  const handleAnalyze = async () => {
  if (!jobDescriptionFile || files.length === 0) {
    alert('Please upload a job description file and at least one CV.');
    return;
  }

  const BATCH_SIZE = 5;
  const totalResults = [];
  setLoading(true);

  try {
    for (let i = 0; i < files.length; i += BATCH_SIZE) {
      const batch = files.slice(i, i + BATCH_SIZE);
      const formData = new FormData();
      formData.append('job_description', jobDescriptionFile);
      formData.append('selectedOptions', JSON.stringify(selectedOptions));
      batch.forEach(file => formData.append('cvs', file));

      const response = await fetch('http://localhost:4780/analyzeManyCvs', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Failed to analyze batch starting at index ${i}`);
      }

      const result = await response.json();
      if (Array.isArray(result.results)) {
        totalResults.push(...result.results);
      }
    }

    setAnalysisResult(totalResults);
    localStorage.setItem('analysisResultMany', JSON.stringify(totalResults));

  } catch (error) {
    console.error('Error analyzing CVs:', error.message);
    alert('Something went wrong while analyzing the CVs.');
  } finally {
    setLoading(false);
  }
};

  
  const handleFileChange = (e) => {
    const newFiles = Array.from(e.target.files);
    const updated = [...files, ...newFiles];
    const unique = Array.from(new Map(updated.map(f => [f.name, f])).values());
    setFiles(unique);
    localStorage.setItem('cvFiles', JSON.stringify(unique.map(file => ({ name: file.name }))));
  };
  
  const removeFile = (name) => {
    const updated = files.filter(file => file.name !== name);
    setFiles(updated);
    localStorage.setItem('cvFiles', JSON.stringify(updated.map(file => ({ name: file.name }))));
  };

  return (
    <div className="ManyCvs">
      <div className="jobCards">
       <div className='description'>
  <label>Upload Job Description (PDF) :</label>
  <input 
    type="file" 
    accept=".pdf,.doc,.docx,.txt" 
    onChange={(e) => {
      const file = e.target.files[0];
      if (file) {
        setJobDescriptionFile(file);
        setJdFileName(file.name);
        localStorage.setItem('jobDescriptionFileName', file.name);
      }
    }} 
  />
  {jdFileName && <p>Selected JD File: {jdFileName}</p>}
</div>
        <div className="parameters">
          <label className="paraHeading">Choose parameters to filter the resumes based on:</label>
          <div className="checkbox-group">
        
            <label>
              <input
                type="checkbox"
                value="percentage"
                checked={selectedOptions.includes("percentage")}
                onChange={handleOptionChange}
                disabled={
                  selectedOptions.includes("all") || 
                  (!selectedOptions.includes("percentage") && selectedOptions.length >= 3)
                }
              />
              Percentage Match
            </label>

            <label>
              <input
                type="checkbox"
                value="similarities"
                checked={selectedOptions.includes("similarities")}
                onChange={handleOptionChange}
                disabled={
                  selectedOptions.includes("all") || 
                  (!selectedOptions.includes("similarities") && selectedOptions.length >= 3)
                }
              />
              Skill Similarities
            </label>

            <label>
              <input
                type="checkbox"
                value="missing"
                checked={selectedOptions.includes("missing")}
                onChange={handleOptionChange}
                disabled={
                  selectedOptions.includes("all") || 
                  (!selectedOptions.includes("missing") && selectedOptions.length >= 3)
                }
              />
              Missing Skills
            </label>

            <label>
              <input
                type="checkbox"
                value="courses"
                checked={selectedOptions.includes("courses")}
                onChange={handleOptionChange}
                disabled={
                  selectedOptions.includes("all") || 
                  (!selectedOptions.includes("courses") && selectedOptions.length >= 3)
                }
              />
              Course Recommendations Based on Missing Skills
            </label>
            <label>
              <input
                type="checkbox"
                value="all"
                checked={selectedOptions.includes("all")}
                onChange={handleOptionChange}
              />
              All Parameters
            </label>
          </div>
        </div>

        <div className="CV-card">
          <label>Upload CVs (PDFs only):</label>
          <input type="file" multiple onChange={handleFileChange} />
          {files.length > 0 && (
            <ul>
              {files.map((file, index) => (
                <li key={index}>
                  {file.name}
                  <button className="removeBtn" onClick={() => removeFile(file.name)}>Remove</button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="btnSection">
          <button onClick={handleAnalyze}>Analyze</button>
        </div>

        {loading ? (
          <div className="dot-loader">
            <span></span><span></span><span></span>
          </div>
        ) : analysisResult && analysisResult.length > 0 && (
          <div className="results">
            <h3>Analysis Summary</h3>
            <div className='output'>
            <div className="cutoff-section"> 
              <label htmlFor="cutoffRange">Set Match Cutoff:</label>
              
              <div className="cutoff-control">
                <input
                  type="range"
                  id="cutoffRange"
                  min="0"
                  max="100"
                  step="1"
                  value={cutoff}
                  onChange={(e) => setCutoff(Number(e.target.value))}
                />
                <input
                  type="number"
                  className="cutoff-number"
                  min="0"
                  max="100"
                  step="1"
                  value={cutoff}
                  onChange={(e) => {
                    const val = Number(e.target.value);
                    if (val >= 0 && val <= 100) setCutoff(val);
                  }}
                />
                <span className="cutoff-percent">%</span>
              </div>

              <button onClick={handleDownloadMatchingCVs}>Download Matching CVs</button>
            </div>

            <div className="table-container">
              <table className="feedback-table">
              <thead>
                <tr>
                  <th>CV Name</th>
                  {(selectedOptions.includes("percentage") || selectedOptions.includes("all")) && <th>Match %</th>}
                  {(selectedOptions.includes("similarities") || selectedOptions.includes("all")) && <th>Similar Skills</th>}
                  {(selectedOptions.includes("missing") || selectedOptions.includes("all")) && <th>Missing Skills</th>}
                  {(selectedOptions.includes("courses") || selectedOptions.includes("all")) && <th>Recommended Courses</th>}
                </tr>
              </thead>
              <tbody>
  {[...analysisResult]
    .sort((a, b) => {
      const aMatch = a.feedback?.match_percentage ?? 0;
      const bMatch = b.feedback?.match_percentage ?? 0;
      const aPasses = aMatch >= cutoff;
      const bPasses = bMatch >= cutoff;

  
      if (aPasses && !bPasses) return -1;
      if (!aPasses && bPasses) return 1;

      
      return bMatch - aMatch;
    })
    .map(({ filename, feedback, error }) => (
      <tr
        key={filename}
        className={feedback?.match_percentage >= cutoff ? 'passed-row' : 'failed-row'}
      >
        <td>{filename}</td>
        {error ? (
          <td
            colSpan={
              1 +
              (selectedOptions.includes("percentage") || selectedOptions.includes("all") ? 1 : 0) +
              (selectedOptions.includes("similarities") || selectedOptions.includes("all") ? 1 : 0) +
              (selectedOptions.includes("missing") || selectedOptions.includes("all") ? 1 : 0) +
              (selectedOptions.includes("courses") || selectedOptions.includes("all") ? 1 : 0)
            }
            style={{ color: 'red' }}
          >
            Error: {error}
          </td>
        ) : (
          <>
            {(selectedOptions.includes("percentage") || selectedOptions.includes("all")) && (
              <td>
                {typeof feedback.match_percentage === 'number'
                  ? `${feedback.match_percentage}%`
                  : 'N/A'}
              </td>
            )}

            {(selectedOptions.includes("similarities") || selectedOptions.includes("all")) && (
              <td>
                {Array.isArray(feedback.similarities) && feedback.similarities.length > 0
                  ? feedback.similarities.join(', ')
                  : 'None'}
              </td>
            )}

            {(selectedOptions.includes("missing") || selectedOptions.includes("all")) && (
              <td>
                {Array.isArray(feedback.missing) && feedback.missing.length > 0
                  ? feedback.missing.join(', ')
                  : 'None'}
              </td>
            )}

            {(selectedOptions.includes("courses") || selectedOptions.includes("all")) && (
              <td>
                {Array.isArray(feedback.course_recommendations) && feedback.course_recommendations.length > 0 ? (
                  <ul>
                    {feedback.course_recommendations.map((course) => (
                      <li key={course.url}>
                        <a href={course.url} target="_blank" rel="noopener noreferrer">{course.name}</a>
                      </li>
                    ))}
                  </ul>
                ) : 'None'}
              </td>
            )}
          </>
        )}
      </tr>
    ))}
</tbody>

            </table>

            </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ManyCvs;