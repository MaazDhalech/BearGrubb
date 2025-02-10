"use client";

import { useState, useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL; // Store API base URL

const Products = () => {
  const [meals, setMeals] = useState(null); // Store meals data
  const [selectedOption, setSelectedOption] = useState(""); // Store selected meal type (Halal, Vegan, etc.)
  const [selectedMealtime, setSelectedMealtime] = useState(""); // Store selected mealtime (Breakfast, Lunch, etc.)

  const fetchMeals = async (mealType) => {
    try {
      const response = await fetch(`${API_URL}/api/${mealType}-meals`); // Dynamic API endpoint
      if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
      const data = await response.json();
      setMeals(data); // Store the fetched data
    } catch (error) {
      console.error(`Error fetching ${mealType} meals:`, error);
    }
  };

  const handleMealTypeChange = (event) => {
    const option = event.target.value;
    setSelectedOption(option);

    if (option === "1") fetchMeals("halal");
    if (option === "2") fetchMeals("vegetarian");
    if (option === "3") fetchMeals("vegan");
  };

  const handleMealtimeChange = (event) => {
    setSelectedMealtime(event.target.value);
  };

  useEffect(() => {
    if (selectedOption) {
      const mealType = selectedOption === "1" ? "halal" 
                     : selectedOption === "2" ? "vegetarian" 
                     : "vegan";
      fetchMeals(mealType);
    }
  }, [selectedOption]);

  // Determine if today is a weekend and set showBrunch accordingly
  const isWeekend = [0, 6].includes(new Date().getDay());
  const [showBrunch, setShowBrunch] = useState(isWeekend);

  useEffect(() => {
    setShowBrunch(isWeekend);
  }, [isWeekend]);

  return (
    <div className="p-4 text-black">
      {/* Meal Type Selection */}
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

      {/* Mealtime Selection */}
      <div className="mb-4">
        <label className="block text-lg font-semibold mb-2">Select a Mealtime:</label>
        <select
          className="select select-bordered w-full max-w-xs p-2 rounded border-gray-300 shadow-sm focus:outline-none focus:ring focus:ring-blue-200"
          onChange={handleMealtimeChange}
          value={selectedMealtime}
          disabled={!selectedOption}
        >
          <option value="" disabled>Select a mealtime</option>
          {!showBrunch && <option value="Breakfast">Breakfast</option>}
          {showBrunch && <option value="Brunch">Brunch</option>}
          {!showBrunch && <option value="Lunch">Lunch</option>}
          <option value="Dinner">Dinner</option>
        </select>
      </div>

      {/* Meals Display */}
      <div className="overflow-x-auto mb-12">
        <table className="table-auto w-full border-collapse border border-gray-300 shadow-sm rounded-lg">
          <thead>
            <tr className="bg-gray-200 text-left">
              <th className="border border-gray-300 p-3 text-lg font-semibold">Dining Place</th>
              <th className="border border-gray-300 p-3 text-lg font-semibold">
                {selectedMealtime || "Select Mealtime"}
              </th>
            </tr>
          </thead>
          <tbody>
            {meals && selectedMealtime ? (
              Object.keys(meals).map((diningHall) => (
                <tr key={diningHall} className="hover:bg-gray-100">
                  <td className="border border-gray-300 p-3 font-medium">{diningHall.replace(/_/g, " ")}</td>
                  <td className="border border-gray-300 p-3">
                    {meals[diningHall][selectedMealtime]?.length > 0
                      ? meals[diningHall][selectedMealtime].join(", ")
                      : "No meals available"}
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
