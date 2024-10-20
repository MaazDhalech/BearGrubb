import React, { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function Component({ data = {} }) {
  const [selectedMeal, setSelectedMeal] = useState('Breakfast'); // Default to 'Breakfast'
  const diningHalls = Object.keys(data);
  const mealTypes = ['Breakfast', 'Brunch', 'Lunch', 'Dinner'];

  const handleMealChange = (meal) => {
    setSelectedMeal(meal);
  };

  return (
    <div className="p-6">
      {/* Dropdown for Meal Type */}
      <div className="flex justify-start mb-4">
        <div className="mr-4">
          <label className="text-sm font-semibold mb-2 block">Select Meal Time:</label>
          <Select onValueChange={handleMealChange}>
            <SelectTrigger className="w-full max-w-[200px] bg-gray-50 border border-gray-300">
              <SelectValue placeholder={selectedMeal} />
            </SelectTrigger>
            <SelectContent>
              {mealTypes.map((meal) => (
                <SelectItem key={meal} value={meal}>
                  {meal}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Dining Halls Table */}
      <div className="overflow-x-auto">
        <Table className="min-w-full table-auto border-collapse border border-gray-200 shadow-lg">
          <TableHeader className="bg-gray-100">
            <TableRow>
              <TableHead className="text-left text-sm font-semibold text-gray-700 p-4 border-b border-gray-200">Dining Hall</TableHead>
              <TableHead className="text-left text-sm font-semibold text-gray-700 p-4 border-b border-gray-200">{selectedMeal}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {diningHalls.map((hall) => (
              <TableRow key={hall} className="hover:bg-gray-50">
                <TableCell className="p-4 border-b border-gray-200 font-medium">{hall.replace(/_/g, ' ')}</TableCell>
                <TableCell className="p-4 border-b border-gray-200">
                  <Select>
                    <SelectTrigger className="w-full max-w-[180px] text-sm bg-gray-50 border border-gray-300 focus:border-blue-500">
                      <SelectValue placeholder="Select a meal" />
                    </SelectTrigger>
                    <SelectContent>
                      {data[hall][selectedMeal]?.length > 0 ? (
                        data[hall][selectedMeal].map((item, index) => (
                          <SelectItem key={`${hall}-${selectedMeal}-${index}`} value={item}>
                            {item}
                          </SelectItem>
                        ))
                      ) : (
                        <SelectItem value="no-meals" disabled>
                          No meals available
                        </SelectItem>
                      )}
                    </SelectContent>
                  </Select>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
