// components/Products.js
"use client";

import { useState, useEffect } from 'react';

const Products = () => {
  const [meals, setMeals] = useState(null);
  const [selectedOption, setSelectedOption] = useState('');

  const fetchHalalMeals = async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/api/halal-meals'); // Flask API endpoint
      const data = await response.json();
      setMeals(data); // Store the fetched data
    } catch (error) {
      console.error('Error fetching halal meals:', error);
    }
  };

  const handleSelectChange = (event) => {
    const option = event.target.value;
    setSelectedOption(option);

    if (option === 'Halal') {
      // Load halal meals if "Halal" option is selected
      fetchHalalMeals();
    } 
    // You can add more options for vegetarian, vegan, etc., if needed
  };

  useEffect(() => {
    void fetchHalalMeals()
  }, [])

  return (
    <div className="p-4 text-black">
    {
      
    }

      <table>
        <thead>
          <th>Dining Place</th>
          <th>breakfast</th>
          <th>lunch</th>
          <th>brunch</th>
          <th>dinner</th>
        </thead>
        <tbody>{
          meals ? <>
            {
              Object.keys(meals).map(name => <tr>
                <td>{name}</td>
                <td>{JSON.stringify(meals[name]['Breakfast'])}</td>
                <td>{JSON.stringify(meals[name]['Lunch'])}</td>
                <td>{JSON.stringify(meals[name]['Brunch'])}</td>
                <td>{JSON.stringify(meals[name]['Dinner'])}</td>
              </tr>)
            }
          </> : null
          }
        </tbody>
      </table>
      <select 
        className="select select-bordered mb-4 w-full max-w-xs" 
        onChange={handleSelectChange}
        value={selectedOption}
      >
        <option value="">Select an option</option>
        <option value="1">Halal</option>
        <option value="2">Vegetarian</option>
        <option value="3">Vegan</option>
      </select>

      {/* Display the halal meals if the API has returned data */}
      {selectedOption === '1' && meals && Object.keys(meals).length > 0 && (
        <div>
          {/* {Object.keys(meals).map((hall) => (
            <div key={hall} className="my-4">
              <h3 className="text-xl font-semibold">{hall}</h3>
              <p><strong>Breakfast:</strong> {meals[hall].breakfast.join(', ')}</p>
              <p><strong>Lunch:</strong> {meals[hall].lunch.join(', ')}</p>
              <p><strong>Dinner:</strong> {meals[hall].dinner.join(', ')}</p>
            </div>
          ))} */}
        </div>
      )}
    </div>
  );
};

export default Products;
