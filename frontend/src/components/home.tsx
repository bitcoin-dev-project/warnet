import React from "react";
import Link from "next/link";
import Image from "next/image";
import BitcoinLogo from "../assests/svgs/bitcoin-logo.svg";
import Machines from "../assests/images/machines.webp";
import styles from "./styles.module.css";

const HomePage = () => {
  return (
    <div
      className={`flex w-full max-w-full min-h-screen overflow-scroll md:grid md:gap-0 md:h-screen md:max-h-screen md:overflow-hidden ${styles.wrapper}`}
    >
      <div className="bg-secondary-transparent-black flex gap-7 flex-col p-5 py-12 md:p-8 xl:p-12 md:py-12 max-w-full md:max-w-xl w-full md:bg-primary-transparent-black z-50">
        <div className="flex flex-col gap-6">
          <section className="flex gap-3 items-center justify-items-center">
            <Image
              src={BitcoinLogo}
              alt="bitcoin logo"
              className="w-12 h-12 md:w-12 md:h-12 xl:w-20 xl:h-20"
            />
            <h2 className="font-bold xl:text-custom-logo text-5xl md:text-5xl xl:text-6xl leading-none text-brand-purple">
              warnet
            </h2>
          </section>
          <p className="text-white dark:text-white text-2xl md:text-2xl lg:text-3xl xl:text-4xl">
            Monitor and analyze the emergent behaviors of P2P networks
          </p>
        </div>

        <div className="text-white dark:text-white flex flex-col gap-9 text-base md:text-lg lg:text-2xl font-normal text-custom-gray">
          <p>Build a stronger, more resilient Bitcoin</p>
          <p>Break the warnet before it comes to mainnet</p>
          <p>Monitor extreme and yet unknown network behaviors</p>
          <Link
            className="py-5 px-6 border-2 text-center text-brand-purple border-brand-purple sm:w-fit whitespace-nowrap font-medium"
            href="https://github.com/bitcoin-dev-project/warnet"
            target="_blank"
          >
            download now
          </Link>
          <Link
            className="text-white dark:text-white py-5 px-6 border-2 text-center sm:w-fit whitespace-nowrap hidden"
            href="/start"
          >
            generate graph
          </Link>
        </div>
      </div>

      <div className="overflow-hidden absolute bottom-0 right-0 z-0">
        <section
          className={`bg-gradient-light-shade h-gradient-height w-gradient-width relative bottom-0 ${styles.gradientRectangle}`}
        ></section>
        <section
          className={`absolute bg-gradient-light-shade h-gradient-height w-gradient-width ${styles.gradientRectangle} ${styles.gradientRectangle1}`}
        ></section>
      </div>

      <div className="hidden md:overflow-hidden md:w-full md:h-screen md:flex md:items-center md:z-20 md:max-w-5xl">
        <Image
          src={Machines}
          alt="a group of machines"
          className="w-full max-w-5xl object-contain"
        />
      </div>
    </div>
  );
};

export default HomePage;
