import Head from 'next/head';
import Products from './components/Products';
import Link from 'next/link';
import DynamicTable from './components/DynamicTable'

const Home = () => {
  const tableData = [
    ['Row 1, Col 1', 'Row 1, Col 2'],
    ['Row 2, Col 1'],
    ['Row 3, Col 1', 'Row 3, Col 2', 'Row 3, Col 3'],
    ['Row 4, Col 1', 'Row 4, Col 2', 'Row 4, Col 3', 'Row 4, Col 4'],
  ];

  return (

    
    <div className="flex flex-col min-h-screen">
      <h1 className="text-2xl font-bold mb-4">Dynamic Table Example</h1>
      <DynamicTable data={tableData} />
      <Head>
        <title>CalInclusiveDining</title>
        <meta name="description" content="A menu of halal, vegetarian, and vegan at Berkeley dining halls." />
        <link 
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap" 
          rel="stylesheet" 
        />
      </Head>

      {/* Navbar */}
      <header className="bg-[#003262] fixed top-0 left-0 w-full z-10 font-sans">
        <div className="container mx-auto p-4 flex items-center justify-between">
          <Link href="/" className="text-white font-bold text-xl hover:text-gray-300">
            Cal Dining
          </Link>
        </div>
      </header>

      <main className="container mx-auto pt-20 flex-grow">
        {/* Gold background row with Etelka text */}
        <div className="bg-[#C3820E] text-white p-4 text-center">
          <h1 className="text-3xl font-bold" style={{ fontFamily: 'Etelka' }}>CalInclusiveDining</h1>
        </div>

        {/* Subtitle with gold border and different color */}
        <h2 className="text-3xl font-bold text-center my-4 border-4 border-[#C3820E] p-4 text-[#003262]" style={{ color: '#003262' }}>
          A menu of halal, vegetarian, and vegan food at Berkeley dining halls.
        </h2>

        {/* Products Component */}
        <Products />
      </main>

      {/* Footer that stretches across the page and touches the bottom */}
      <footer className="bg-[#003262] text-white p-4 w-full flex justify-center items-center fixed bottom-0 left-0">
        <div className="container mx-auto flex justify-between items-center">
          {/* Social Media Icons */}
          <div className="flex space-x-6">
            <a href="#" className="hover:text-gray-400">
              <svg className="w-5 h-5" fill="currentColor" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M22.46 6.03c-.77.35-1.59.58-2.46.68a4.15 4.15 0 001.82-2.3 8.3 8.3 0 01-2.63 1 4.14 4.14 0 00-7.05 3.77A11.74 11.74 0 012.92 5a4.15 4.15 0 001.29 5.52A4.12 4.12 0 012 10v.05c0 1.92 1.36 3.53 3.16 3.89a4.13 4.13 0 01-1.87.07A4.14 4.14 0 007 17.74a8.3 8.3 0 01-5.12 1.76A8.52 8.52 0 002.77 20a11.7 11.7 0 006.3 1.85c7.55 0 11.68-6.25 11.68-11.67v-.53a8.35 8.35 0 002.05-2.12l-.02-.05z"/></svg>
            </a>
            <a href="#" className="hover:text-gray-400">
              <svg className="w-5 h-5" fill="currentColor" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 2.04c-5.48 0-9.96 4.48-9.96 9.96 0 4.42 3.64 8.08 8.32 8.84v-6.26h-2.5v-2.45h2.5v-1.87c0-2.47 1.5-3.8 3.69-3.8 1.05 0 1.95.08 2.22.11v2.56h-1.52c-1.2 0-1.43.57-1.43 1.41v1.85h2.87l-.37 2.45h-2.5v6.26c4.68-.76 8.32-4.42 8.32-8.84 0-5.48-4.48-9.96-9.96-9.96z"/></svg>
            </a>
            <a href="#" className="hover:text-gray-400">
              <svg className="w-5 h-5" fill="currentColor" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M22.23 0H1.77C.8 0 0 .78 0 1.75v20.5C0 23.22.8 24 1.77 24H22.23c.97 0 1.77-.78 1.77-1.75V1.75C24 .78 23.2 0 22.23 0zM7.19 20.49H3.95V9h3.24v11.49zM5.57 7.77a1.88 1.88 0 110-3.76 1.88 1.88 0 010 3.76zM20.49 20.49h-3.24V14.5c0-1.43-.02-3.26-1.99-3.26-1.99 0-2.29 1.56-2.29 3.17v6.08H10.73V9h3.11v1.57h.04c.43-.83 1.48-1.7 3.06-1.7 3.27 0 3.87 2.15 3.87 4.95v6.67z"/></svg>
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Home;
