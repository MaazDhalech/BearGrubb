// components/Products.js
"use client";

import { useState, useEffect } from 'react';

const Products = () => {
  const [items, setItems] = useState([]);
  const [selectedTitle, setSelectedTitle] = useState('');
  const [selectedOption, setSelectedOption] = useState('');

  const fetchData = async (url) => {
    const response = await fetch(url);
    const data = await response.json();

    // Keep the data as an array of products
    setItems(data.products); // Assuming products will be fetched
  };

  const handleSelectChange = (event) => {
    const option = event.target.value;
    setSelectedOption(option);

    if (option === '1') {
      // Load the first title
      setSelectedTitle(items.length > 0 ? items[0].title : '');
    } else if (option === '2') {
      // Load the second title
      setSelectedTitle(items.length > 1 ? items[1].title : '');
    }
  };

  // Fetch products when the component mounts
  useEffect(() => {
    fetchData('https://dummyjson.com/products');
  }, []);

  return (
    <div className="p-4">
      <select 
        className="select select-bordered mb-4 w-full max-w-xs" 
        onChange={handleSelectChange}
        value={selectedOption}
      >
        <option value="">Select an option</option>
        <option value="1">1</option>
        <option value="2">2</option>
      </select>

      {/* Textbox to display the selected title */}
      <input
        type="text"
        value={selectedTitle}
        readOnly
        className="input input-bordered w-full mb-4"
      />
    </div>
  );
};

export default Products;
