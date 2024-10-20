// components/DynamicTable.js
import React from 'react';

const DynamicTable = ({ data }) => {
  // Determine the number of columns based on the longest array in the data
  const columnCount = Math.max(...data.map(row => row.length));

  return (
    <div className="overflow-x-auto">
      <table className="table w-full">
        <thead>
          <tr>
            {data[0].map((_, index) => (
              <th key={index}>Column {index + 1}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {Array.from({ length: columnCount }, (_, colIndex) => (
                <td key={colIndex}>
                  {row[colIndex] || '-'} {/* Show '-' if there's no data */}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default DynamicTable;
