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
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Dining Hall</TableHead>
          {mealTypes.map((meal) => (
            <TableHead key={meal}>{meal}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {diningHalls.map((hall) => (
          <TableRow key={hall}>
            <TableCell className="font-medium">{hall.replace(/_/g, ' ')}</TableCell>
            {mealTypes.map((meal) => (
              <TableCell key={`${hall}-${meal}`}>
                <Select>
                  <SelectTrigger className="w-[180px]">
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
  )
}