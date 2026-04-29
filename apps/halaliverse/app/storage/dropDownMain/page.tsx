"use client"; // This line should be at the top of your file

import Head from 'next/head';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function Home() {
  const [selectedOption, setSelectedOption] = useState<string>("");
  const router = useRouter();

  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedOption(event.target.value);
  };

  const handleGoClick = () => {
    if (selectedOption === "1") {
      router.push('/halal');
    } else if (selectedOption === "2") {
      router.push('/vegetarian');
    } else if (selectedOption === "3") {
      router.push('/vegan');
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gray-100">
      <Head>
        <title>Halaliversity</title>
      </Head>

      {/* Title */}
      <h1 className="text-5xl font-bold mb-8">BerkeleyInclusiveDining</h1>

      {/* Select Menu and Button */}
      <div className="flex items-center mb-8">
        <select 
          className="select select-bordered w-48" 
          value={selectedOption} 
          onChange={handleChange}
        >
          <option value="" disabled>Select an option</option>
          <option value="1">Halal</option>
          <option value="2">Vegetarian</option>
          <option value="3">Vegan</option>
        </select>
        <button 
          className="btn btn-primary ml-4" 
          onClick={handleGoClick} 
          disabled={!selectedOption} // Disable button when no option is selected
        >
          Go
        </button>
      </div>

      {/* Placeholder Information */}
      <div className="text-center">
        <p className="text-lg">
          PLACEHOLDER TEXT Halaliversity provides students with information about halal menu items for colleges all over the US. PLACEHOLDER TEXT
        </p>
      </div>
    </div>
  );
}
