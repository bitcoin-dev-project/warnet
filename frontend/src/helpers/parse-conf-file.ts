  export const parseBitcoinConf = (content: string, name:string) => {
    const lines = content.split('\n');
    const config: Record<string, string> = {};

    lines.forEach((line) => {
      const [key, value] = line.split('=');

      if (key && value) {
        config[key.trim()] = value.trim();
      }
    });
    return {name, ...config}
  }
