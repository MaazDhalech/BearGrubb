// components/Products.js
"use client";

import { useState, useEffect } from 'react';

const Products = () => {
  const [meals, setMeals] = useState(null); // Store meals data
  const [selectedOption, setSelectedOption] = useState(''); // Store selected meal type (Halal, Vegan, etc.)
  const [selectedMealtime, setSelectedMealtime] = useState(''); // Store selected mealtime (Breakfast, Lunch, etc.)

  const fetchHalalMeals = async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/api/halal-meals'); // Flask API endpoint
      const data = await response.json();
      setMeals(data); // Store the fetched data
    } catch (error) {
      console.error('Error fetching halal meals:', error);
    }
  };
  const fetchVeganMeals = async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/api/vegan-meals'); // Flask API endpoint
      const data = await response.json();
      setMeals(data); // Store the fetched data
    } catch (error) {
      console.error('Error fetching vegan meals:', error);
    }
  };
  const fetchVegetarianMeals = async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/api/vegetarian-meals'); // Flask API endpoint
      const data = await response.json();
      setMeals(data); // Store the fetched data
    } catch (error) {
      console.error('Error fetching vegetarian meals:', error);
    }
  };
  const handleMealTypeChange = (event) => {
    const option = event.target.value;
    setSelectedOption(option);

    if (option === '1') {
      // Load halal meals if "Halal" option is selected
      fetchHalalMeals();
    }
    if (option === '2') {
      fetchVegetarianMeals();
    }
    if (option === '3') {
      fetchVeganMeals();
    }
  };

  const handleMealtimeChange = (event) => {
    setSelectedMealtime(event.target.value);
  };

  useEffect(() => {
    if (selectedOption === '1') {
      fetchHalalMeals(); // Fetch halal meals when Halal is selected
    }
  }, [selectedOption]);
  useEffect(() => {
    if (selectedOption === '2') {
      fetchVegetarianMeals(); // Fetch vegetarian meals when selected
    }
  }, [selectedOption]);
  useEffect(() => {
    if (selectedOption === '3') {
      fetchVeganMeals(); // Fetch vegan meals when selected
    }
  }, [selectedOption]);

  // Determine if today is a weekend and set showBrunch accordingly
  const isWeekend = (new Date().getDay() === 6) || (new Date().getDay() === 0);

  // State variable to control which options are shown, initialized based on the day
  const [showBrunch, setShowBrunch] = useState(isWeekend);

  useEffect(() => {
    // Ensure the state is updated if the component re-renders on a different day
    setShowBrunch(isWeekend);
  }, [isWeekend]);

  return (
    <div className="p-4 text-black">
      {/* First dropdown for meal type selection */}
      <div className="mb-4">
        <label className="block text-lg font-semibold mb-2">Select a Meal Type:</label>
        <select
          className="select select-bordered w-full max-w-xs p-2 rounded border-gray-300 shadow-sm focus:outline-none focus:ring focus:ring-blue-200"
          onChange={handleMealTypeChange}
          value={selectedOption}
        >
          <option value="" disabled>Select a meal type</option>
          <option value="1">Halal</option>
          <option value="2">Vegetarian</option>
          <option value="3">Vegan</option>
        </select>
      </div>

      {/* Second dropdown for mealtime selection */}
      <div className="mb-4">
        <label className="block text-lg font-semibold mb-2">Select a Mealtime:</label>
        <select
          className="select select-bordered w-full max-w-xs p-2 rounded border-gray-300 shadow-sm focus:outline-none focus:ring focus:ring-blue-200"
          onChange={handleMealtimeChange}
          value={selectedMealtime}
          disabled={!selectedOption} // Disable if meal type is not selected
        >
          <option value="" disabled>Select a mealtime</option>
          {!showBrunch && <option value="Breakfast">Breakfast</option>}
          {showBrunch && <option value="Brunch">Brunch</option>}
          {!showBrunch && <option value="Lunch">Lunch</option>}
          <option value="Dinner">Dinner</option>
        </select>
      </div>

      {/* Display the meals table with spacing below */}
      <div className="overflow-x-auto mb-12"> {/* Add margin-bottom to create space before footer */}
        <table className="table-auto w-full border-collapse border border-gray-300 shadow-sm rounded-lg">
          <thead>
            <tr className="bg-gray-200 text-left">
              <th className="border border-gray-300 p-3 text-lg font-semibold">Dining Place</th>
              <th className="border border-gray-300 p-3 text-lg font-semibold">
                {selectedMealtime || 'Select Mealtime'}
              </th>
            </tr>
          </thead>
          <tbody>
            {meals && selectedMealtime ? (
              Object.keys(meals).map((diningHall) => (
                <tr key={diningHall} className="hover:bg-gray-100">
                  <td className="border border-gray-300 p-3 font-medium">{diningHall.replace(/_/g, ' ')}</td>
                  <td className="border border-gray-300 p-3">
                    {meals[diningHall][selectedMealtime]?.length > 0
                      ? meals[diningHall][selectedMealtime].join(', ')
                      : 'No meals available'}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="2" className="border border-gray-300 p-3 text-center text-gray-500">
                  Select a meal type and mealtime to see results.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Products;
