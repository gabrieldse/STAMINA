
export type MissionConfig = {
  name: string;
  date: string;
  duration: number;
  sunlight: number;
  earth: number;
};

export type LandingSite = {
  id: string;
  name: string;
  description: string;
};

export const LANDING_SITES: LandingSite[] = [
  {
    id: "alpha",
    name: "Site Alpha",
    description: "Candidate site near Shackleton crater.",
  },
  {
    id: "beta",
    name: "Site Beta",
    description: "Alternative landing location.",
  },
  {
    id: "gamma",
    name: "Site Gamma",
    description: "Additional candidate location.",
  },
];
