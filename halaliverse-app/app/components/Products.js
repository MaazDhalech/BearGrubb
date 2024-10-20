"use client";

import { useState, useEffect } from 'react';

const Products = () => {
  const [meals, setMeals] = useState(null);  // Stores the fetched meal data
  const [selectedOption, setSelectedOption] = useState('');  // Tracks the dropdown selection

  // Function to fetch halal meals from the Flask API
  const fetchHalalMeals = async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/api/halal-meals');  // Flask API endpoint
      const data = await response.json();
      setMeals(data);  // Store the fetched meal data
    } catch (error) {
      console.error('Error fetching halal meals:', error);
    }
  };

  // Handle dropdown selection change
  const handleSelectChange = (event) => {
    const option = event.target.value;
    setSelectedOption(option);

    if (option === 'Halal') {
      // Fetch halal meals when 'Halal' is selected
      fetchHalalMeals();
    } 
    // You can add more options for vegetarian, vegan, etc., if needed
  };

  return (
    <div className="p-4 text-black">
      {/* Dropdown for selecting meal type */}
      <select 
        className="select select-bordered mb-4 w-full max-w-xs" 
        onChange={handleSelectChange}
        value={selectedOption}
      >
        <option value="">Select an option</option>
        <option value="Halal">Halal</option>
        <option value="Vegetarian">Vegetarian</option>
        <option value="Vegan">Vegan</option>
      </select>

      {/* Display the meals table only when data is available */}
      {meals && (
        <table className="min-w-full border-collapse border border-gray-300">
          <thead>
            <tr>
              <th className="border border-gray-300 px-4 py-2">Dining Hall</th>
              <th className="border border-gray-300 px-4 py-2">Breakfast</th>
              <th className="border border-gray-300 px-4 py-2">Lunch</th>
              <th className="border border-gray-300 px-4 py-2">Brunch</th>
              <th className="border border-gray-300 px-4 py-2">Dinner</th>
            </tr>
          </thead>
          <tbody>
            {
              Object.keys(meals).map(hall => (
                <tr key={hall}>
                  <td className="border border-gray-300 px-4 py-2">{hall.replace(/_/g, ' ')}</td>
                  <td className="border border-gray-300 px-4 py-2">{meals[hall].Breakfast ? meals[hall].Breakfast.join(', ') : 'No breakfast'}</td>
                  <td className="border border-gray-300 px-4 py-2">{meals[hall].Lunch ? meals[hall].Lunch.join(', ') : 'No lunch'}</td>
                  <td className="border border-gray-300 px-4 py-2">{meals[hall].Brunch ? meals[hall].Brunch.join(', ') : 'No brunch'}</td>
                  <td className="border border-gray-300 px-4 py-2">{meals[hall].Dinner ? meals[hall].Dinner.join(', ') : 'No dinner'}</td>
                </tr>
              ))
            }
          </tbody>
        </table>
      )}
    </div>
  );
};

export default Products;
