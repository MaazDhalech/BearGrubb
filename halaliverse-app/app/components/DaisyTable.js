// components/DaisyTable.js
import React from 'react';

const DaisyTable = ({ jsonData }) => {
  // Extract keys (columns) from the JSON structure
  const columns = Object.keys(jsonData);
  const rowCount = Math.max(...columns.map((col) => jsonData[col].length));

  return (
    <div className="overflow-x-auto">
      <table className="table w-full">
        {/* Table Head */}
        <thead>
          <tr>
            {columns.map((col, index) => (
              <th key={index}>{col}</th>
            ))}
          </tr>
        </thead>
        {/* Table Body */}
        <tbody>
          {Array.from({ length: rowCount }).map((_, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((col, colIndex) => (
                <td key={colIndex}>
                  {jsonData[col][rowIndex] || '-'} {/* Fallback for missing data */}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default DaisyTable;
