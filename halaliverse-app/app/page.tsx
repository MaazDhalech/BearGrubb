import Head from 'next/head';
import Products from './components/Products';

const Home = () => {
  return (
    <div>
      <Head>
        <title>Product and Post List</title>
        <meta name="description" content="A list of products and posts." />
      </Head>
      <main className="container mx-auto">
        <h1 className="text-3xl font-bold text-center my-4">Product and Post List</h1>
        <Products />
      </main>
    </div>
  );
};

export default Home;
