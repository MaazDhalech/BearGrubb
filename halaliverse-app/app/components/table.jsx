import React from 'react'
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

export default function Component({ data = {} }) {
  const diningHalls = Object.keys(data)
  const mealTypes = ['Breakfast', 'Brunch', 'Lunch', 'Dinner']

  return (
    <div className="overflow-x-auto">
      <Table className="min-w-full table-auto border-collapse border border-gray-200 shadow-lg">
        <TableHeader className="bg-gray-100">
          <TableRow>
            <TableHead className="text-left text-sm font-semibold text-gray-700 p-4 border-b border-gray-200">Dining Hall</TableHead>
            {mealTypes.map((meal) => (
              <TableHead key={meal} className="text-left text-sm font-semibold text-gray-700 p-4 border-b border-gray-200">{meal}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {diningHalls.map((hall) => (
            <TableRow key={hall} className="hover:bg-gray-50">
              <TableCell className="p-4 border-b border-gray-200 font-medium">{hall.replace(/_/g, ' ')}</TableCell>
              {mealTypes.map((meal) => (
                <TableCell key={`${hall}-${meal}`} className="p-4 border-b border-gray-200">
                  <Select>
                    <SelectTrigger className="w-full max-w-[180px] text-sm bg-gray-50 border border-gray-300 focus:border-blue-500">
                      <SelectValue placeholder="Select a meal" />
                    </SelectTrigger>
                    <SelectContent>
                      {data[hall][meal].length > 0 ? (
                        data[hall][meal].map((item, index) => (
                          <SelectItem key={`${hall}-${meal}-${index}`} value={item}>
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
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
