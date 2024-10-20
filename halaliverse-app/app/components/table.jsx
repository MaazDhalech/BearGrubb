import React, { useState, useEffect } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export default function MealTable({ data = {} }) {
  const diningHalls = Object.keys(data)
  const mealTypes = ['Breakfast', 'Brunch', 'Lunch', 'Dinner']

  const [selectedDiningHall, setSelectedDiningHall] = useState(diningHalls[0] || '');
  const [selectedMealType, setSelectedMealType] = useState(mealTypes[0] || '');
  const [selectedMeals, setSelectedMeals] = useState([]);

  const handleDiningHallChange = (hall) => {
    setSelectedDiningHall(hall);
    if (data[hall] && data[hall][selectedMealType]) {
      setSelectedMeals(data[hall][selectedMealType]);
    } else {
      setSelectedMeals([]);
    }
  };

  const handleMealTypeChange = (meal) => {
    setSelectedMealType(meal);
    if (data[selectedDiningHall] && data[selectedDiningHall][meal]) {
      setSelectedMeals(data[selectedDiningHall][meal]);
    } else {
      setSelectedMeals([]);
    }
  };

  useEffect(() => {
    // When the component mounts or when dining hall/meal type is changed, update meals
    if (selectedDiningHall && selectedMealType) {
      if (data[selectedDiningHall] && data[selectedDiningHall][selectedMealType]) {
        setSelectedMeals(data[selectedDiningHall][selectedMealType]);
      } else {
        setSelectedMeals([]);
      }
    }
  }, [selectedDiningHall, selectedMealType, data]);

  return (
    <div>
      <div className="flex mb-4 space-x-4">
        {/* Dropdown for selecting the dining hall */}
        <Select onValueChange={handleDiningHallChange} defaultValue={selectedDiningHall}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Select Dining Hall" />
          </SelectTrigger>
          <SelectContent>
            {diningHalls.map((hall) => (
              <SelectItem key={hall} value={hall}>
                {hall.replace(/_/g, ' ')}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Dropdown for selecting the meal type */}
        <Select onValueChange={handleMealTypeChange} defaultValue={selectedMealType}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Select Mealtime" />
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

      {/* Meal Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{selectedDiningHall.replace(/_/g, ' ')}</TableHead>
            <TableHead>{selectedMealType}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {selectedMeals.length > 0 ? (
            selectedMeals.map((item, index) => (
              <TableRow key={`${selectedDiningHall}-${selectedMealType}-${index}`}>
                <TableCell>{item}</TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={2} className="text-center">
                No meals available
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
